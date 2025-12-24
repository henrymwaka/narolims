# lims_core/signals.py
from __future__ import annotations

from threading import local

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail

from lims_core.models import (
    AuditLog,
    Project,
    Sample,
    Experiment,
    InventoryItem,
    UserRole,
    WorkflowTransition,
)

User = get_user_model()

# ===============================================================
# Thread-local user storage (safe + explicit)
# ===============================================================
_state = local()


def set_current_user(user):
    _state.user = user


def get_current_user():
    return getattr(_state, "user", None)


# ===============================================================
# Utilities
# ===============================================================
def _resolve_laboratory(instance):
    if hasattr(instance, "laboratory") and instance.laboratory:
        return instance.laboratory
    return None


def _log(action: str, instance, details: dict | None = None):
    user = get_current_user()
    lab = _resolve_laboratory(instance)

    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        laboratory=lab,
        action=action,
        details=details or {
            "model": instance.__class__.__name__,
            "object_id": instance.pk,
        },
    )


def _safe_username(user) -> str:
    if not user:
        return "system"
    try:
        return user.get_username()
    except Exception:
        return getattr(user, "username", "user")


# ===============================================================
# CREATE / UPDATE audit (core domain objects)
# ===============================================================
@receiver(post_save)
def audit_create_update(sender, instance, created, **kwargs):
    if sender not in {
        Project,
        Sample,
        Experiment,
        InventoryItem,
        UserRole,
    }:
        return

    action = "CREATE" if created else "UPDATE"
    _log(action, instance)


# ===============================================================
# DELETE audit (core domain objects)
# ===============================================================
@receiver(post_delete)
def audit_delete(sender, instance, **kwargs):
    if sender not in {
        Project,
        Sample,
        Experiment,
        InventoryItem,
        UserRole,
    }:
        return

    _log("DELETE", instance)


# ===============================================================
# WORKFLOW TRANSITIONS (Phase 11.5)
# ===============================================================
@receiver(post_save, sender=WorkflowTransition)
def audit_workflow_transition(sender, instance: WorkflowTransition, created: bool, **kwargs):
    """
    Handles side effects of workflow transitions:
    - audit log entry
    - optional email notification

    This runs AFTER executor commits the transition.
    """
    if not created:
        return

    # -----------------------------------------------------------
    # 1. Audit log entry (single source of truth)
    # -----------------------------------------------------------
    AuditLog.objects.create(
        user=instance.performed_by,
        laboratory=instance.laboratory,
        action=(
            f"WORKFLOW {instance.kind.upper()} {instance.object_id}: "
            f"{instance.from_status} -> {instance.to_status}"
        ),
        details={
            "kind": instance.kind,
            "object_id": instance.object_id,
            "from": instance.from_status,
            "to": instance.to_status,
        },
    )

    # -----------------------------------------------------------
    # 2. Optional email notification (feature-flagged)
    # -----------------------------------------------------------
    if not getattr(settings, "WORKFLOW_EMAIL_NOTIFICATIONS", False):
        return

    recipients = getattr(settings, "WORKFLOW_NOTIFY_EMAILS", None)
    if not recipients:
        return

    subject = (
        f"[NARO-LIMS] {instance.kind.upper()} {instance.object_id} "
        f"{instance.from_status} → {instance.to_status}"
    )

    body = "\n".join(
        [
            "Workflow transition recorded.",
            "",
            f"Kind: {instance.kind}",
            f"Object ID: {instance.object_id}",
            f"Laboratory: {instance.laboratory}",
            f"From: {instance.from_status}",
            f"To: {instance.to_status}",
            f"By: {_safe_username(instance.performed_by)}",
            f"At: {instance.created_at}",
        ]
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=list(recipients),
            fail_silently=True,
        )
    except Exception:
        pass
