# lims_core/mixins.py
from __future__ import annotations

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import UserRole

try:
    from .models import Laboratory
except Exception:
    Laboratory = None


# ===============================================================
# Utilities
# ===============================================================

def _model_has_field(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except Exception:
        return False


def _get_user_scope(user):
    """
    Returns:
      - lab_ids: labs user can access directly
      - institute_ids: institutes user can access
    None means unrestricted (superuser).
    """
    if not user or not user.is_authenticated:
        return set(), set()

    if getattr(user, "is_superuser", False):
        return None, None

    qs = UserRole.objects.filter(user=user)

    lab_ids = set()
    institute_ids = set()

    if _model_has_field(qs.model, "laboratory"):
        lab_ids |= set(
            qs.exclude(laboratory__isnull=True)
              .values_list("laboratory_id", flat=True)
        )

    if _model_has_field(qs.model, "institute"):
        institute_ids |= set(
            qs.exclude(institute__isnull=True)
              .values_list("institute_id", flat=True)
        )

    if institute_ids and Laboratory and _model_has_field(Laboratory, "institute"):
        lab_ids |= set(
            Laboratory.objects.filter(
                institute_id__in=institute_ids
            ).values_list("id", flat=True)
        )

    return lab_ids, institute_ids


def _deny_if_payload_has(request, fields: list[str], message: str):
    """
    Reject requests that attempt to mutate server-controlled fields.
    Makes violations noisy and testable.
    """
    incoming = getattr(request, "data", {}) or {}
    present = [f for f in fields if f in incoming]
    if present:
        raise ValidationError({f: message for f in present})


# ===============================================================
# Lab-scoped queryset mixin (READ)
# ===============================================================

class LabScopedQuerysetMixin:
    """
    Enforces lab scoping for models with a `laboratory` FK.
    """

    lab_field_name = "laboratory"

    def get_allowed_lab_ids(self):
        lab_ids, _ = _get_user_scope(self.request.user)
        return lab_ids  # None means unrestricted

    def get_scoped_queryset(self, base_qs):
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return base_qs.none()

        if not _model_has_field(base_qs.model, self.lab_field_name):
            return base_qs

        lab_ids = self.get_allowed_lab_ids()

        # superuser global read
        if lab_ids is None:
            return base_qs

        if not lab_ids:
            return base_qs.none()

        return base_qs.filter(
            **{f"{self.lab_field_name}_id__in": list(lab_ids)}
        )


# ===============================================================
# Lab-scoped create mixin (WRITE)
# ===============================================================

class LabScopedCreateMixin:
    """
    On create:
      - laboratory is server-controlled
      - auto-assign only if user has exactly one allowed lab
    """

    lab_field_name = "laboratory"

    def _incoming_lab_id(self, serializer):
        vd = getattr(serializer, "validated_data", {}) or {}
        lab = vd.get(self.lab_field_name)
        if lab is not None:
            return getattr(lab, "id", None)
        return vd.get(f"{self.lab_field_name}_id")

    def assert_lab_allowed(self, laboratory_id: int):
        allowed = self.get_allowed_lab_ids()
        if allowed is None:
            return
        if not allowed or int(laboratory_id) not in set(map(int, allowed)):
            raise PermissionDenied("You do not have access to this laboratory.")

    def perform_create(self, serializer):
        model_cls = serializer.Meta.model

        if not _model_has_field(model_cls, self.lab_field_name):
            return serializer.save()

        lab_id = self._incoming_lab_id(serializer)
        allowed = self.get_allowed_lab_ids()

        if not lab_id:
            if allowed is None:
                raise PermissionDenied("Superuser must explicitly specify laboratory.")
            allowed = list(allowed or [])
            if len(allowed) == 1:
                return serializer.save(
                    **{f"{self.lab_field_name}_id": allowed[0]}
                )
            raise PermissionDenied("laboratory is required.")

        self.assert_lab_allowed(lab_id)
        return serializer.save()


# ===============================================================
# Audit logging
# ===============================================================

class AuditLogMixin:
    """
    Emits CREATE / UPDATE / DELETE audit records.
    Never breaks the request if logging fails.
    """

    def _guess_lab_id(self, instance):
        if instance and _model_has_field(instance.__class__, "laboratory"):
            return getattr(instance, "laboratory_id", None)
        return None

    def _log(self, user, action, details=None, lab_id=None):
        try:
            from .models import AuditLog

            payload = {
                "user": user if user and user.is_authenticated else None,
                "action": action,
                "details": details or {},
            }
            if lab_id and _model_has_field(AuditLog, "laboratory"):
                payload["laboratory_id"] = lab_id

            AuditLog.objects.create(**payload)
        except Exception:
            pass

    def perform_create(self, serializer):
        instance = serializer.save()
        self._log(
            self.request.user,
            f"CREATE {instance.__class__.__name__}",
            {"id": instance.id},
            self._guess_lab_id(instance),
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        self._log(
            self.request.user,
            f"UPDATE {instance.__class__.__name__}",
            {"id": instance.id},
            self._guess_lab_id(instance),
        )

    def perform_destroy(self, instance):
        obj_id = getattr(instance, "id", None)
        lab_id = self._guess_lab_id(instance)
        super().perform_destroy(instance)
        self._log(
            self.request.user,
            f"DELETE {instance.__class__.__name__}",
            {"id": obj_id},
            lab_id,
        )


# ===============================================================
# Workflow Transition Enforcement (View-level)
# ===============================================================

from .workflows import validate_transition


class WorkflowTransitionMixin:
    """
    Enforces valid workflow transitions for models with a `status` field.

    ViewSets using this mixin must define:
      - workflow_kind = "sample" | "experiment"
    """

    workflow_kind: str = None

    def perform_update(self, serializer):
        instance = self.get_object()

        if self.workflow_kind and "status" in serializer.validated_data:
            old_status = getattr(instance, "status", None)
            new_status = serializer.validated_data["status"]

            try:
                validate_transition(
                    kind=self.workflow_kind,
                    old=old_status,
                    new=new_status,
                )
            except ValueError as e:
                raise ValidationError({"status": str(e)})

        return super().perform_update(serializer)


# ===============================================================
# Workflow Write Guard (Model-level, HARD ENFORCEMENT)
# ===============================================================

class WorkflowWriteGuardMixin(models.Model):
    """
    HARD guard: prevents direct modification of workflow-controlled fields.

    This ensures:
      - No `obj.status = X; obj.save()`
      - No silent serializer bypass
      - Only workflow engine can change state (via .update())
    """

    WORKFLOW_FIELD = "status"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None and self.WORKFLOW_FIELD:
            old = (
                self.__class__.objects
                .filter(pk=self.pk)
                .values_list(self.WORKFLOW_FIELD, flat=True)
                .first()
            )
            new = getattr(self, self.WORKFLOW_FIELD, None)

            if old != new:
                raise DjangoPermissionDenied(
                    f"Direct modification of '{self.WORKFLOW_FIELD}' is forbidden. "
                    "Use execute_transition()."
                )

        return super().save(*args, **kwargs)
