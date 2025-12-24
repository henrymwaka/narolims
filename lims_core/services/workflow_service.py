# lims_core/services/workflow_service.py
"""
Authoritative workflow execution service.

All status transitions MUST go through this service.
Never update status directly in views or serializers.
"""

from typing import Optional

from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied

from lims_core.workflows import (
    validate_transition,
    required_roles,
)
from lims_core.models import WorkflowTransition, UserRole


# ===============================================================
# Helpers
# ===============================================================

def _get_user_roles(user, laboratory_id: Optional[int]) -> set[str]:
    """
    Resolve effective roles for a user in a lab context.
    Superusers bypass role checks.
    """
    if not user or not user.is_authenticated:
        return set()

    if user.is_superuser:
        return {"ADMIN"}

    qs = UserRole.objects.filter(user=user)

    if laboratory_id:
        qs = qs.filter(laboratory_id=laboratory_id)

    return set(qs.values_list("role", flat=True))


# ===============================================================
# Core service
# ===============================================================

@transaction.atomic
def perform_workflow_transition(
    *,
    instance,
    kind: str,
    new_status: str,
    user,
):
    """
    Execute a workflow transition safely.

    Parameters
    ----------
    instance:
        Sample or Experiment instance
    kind:
        "sample" | "experiment"
    new_status:
        Target status
    user:
        Authenticated user performing the action
    """

    old_status = getattr(instance, "status", None)
    new_status = (new_status or "").strip().upper()

    # 1. Structural validation
    try:
        validate_transition(
            kind=kind,
            old=old_status,
            new=new_status,
        )
    except ValueError as e:
        raise ValidationError({"status": str(e)})

    # 2. Role enforcement
    lab_id = getattr(instance, "laboratory_id", None)
    required = required_roles(kind, old_status, new_status)

    user_roles = _get_user_roles(user, lab_id)

    if required and not (user_roles & required):
        raise PermissionDenied(
            f"Transition {old_status} → {new_status} "
            f"requires role(s): {', '.join(sorted(required))}"
        )

    # 3. Persist transition event
    WorkflowTransition.objects.create(
        kind=kind,
        object_id=instance.pk,
        from_status=old_status,
        to_status=new_status,
        performed_by=user if user and user.is_authenticated else None,
        laboratory_id=lab_id,
    )

    # 4. Apply status
    instance.status = new_status
    instance.save(update_fields=["status"])

    return instance
