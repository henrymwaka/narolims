# lims_core/views_workflow_runtime.py
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.core.exceptions import ObjectDoesNotExist, FieldDoesNotExist
from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from lims_core.models import (
    Sample,
    Experiment,
    UserRole,
    WorkflowEvent,
)

from lims_core.workflows import (
    required_roles,
)

from lims_core.workflows.executor import execute_transition
from lims_core.workflows.sla import get_sla
from lims_core.workflows.runtime import (
    enforce_metadata_gate,
    WorkflowBlocked,
)


# ===============================================================
# OpenAPI response schemas (contract lock)
# ===============================================================

WORKFLOW_SLA_SCHEMA = {
    "applies": bool,
    "status": str,
    "severity": (str, type(None)),
    "entered_at": (str, type(None)),
    "age_seconds": (int, type(None)),
    "warn_after_seconds": (int, type(None)),
    "breach_after_seconds": (int, type(None)),
    "remaining_seconds": (int, type(None)),
}

WORKFLOW_RUNTIME_SCHEMA = {
    "id": int,
    "kind": str,
    "status": str,
    "entered_at": (str, type(None)),
    "sla": WORKFLOW_SLA_SCHEMA,
}

WORKFLOW_PATCH_SCHEMA = {
    "id": int,
    "kind": str,
    "from": str,
    "to": str,
    "status": str,
    "entered_at": (str, type(None)),
    "sla": WORKFLOW_SLA_SCHEMA,
}

WORKFLOW_TIMELINE_SCHEMA = {
    "id": int,
    "kind": str,
    "status": str,
    "entered_at": (str, type(None)),
    "sla": WORKFLOW_SLA_SCHEMA,
    "timeline": list,
}


# ===============================================================
# Helpers
# ===============================================================

def _model_has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _get_model_for_kind(kind: str):
    kind = (kind or "").strip().lower()
    if kind == "sample":
        return Sample
    if kind == "experiment":
        return Experiment
    raise ValidationError({"kind": "Unknown workflow kind."})


def _normalize_status(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _get_target_status(data):
    if not isinstance(data, dict):
        return None
    if "status" in data:
        return _normalize_status(data["status"])
    if "to" in data:
        return _normalize_status(data["to"])
    return None


def _get_comment(data) -> str:
    if not isinstance(data, dict):
        return ""
    c = data.get("comment", "")
    return str(c).strip() if c is not None else ""


def _get_user_roles(user, laboratory) -> set[str]:
    if user.is_superuser:
        return {"ADMIN"}

    if not laboratory:
        return set()

    return set(
        UserRole.objects.filter(
            user=user,
            laboratory=laboratory,
        ).values_list("role", flat=True)
    )


def _ensure_laboratory_access_or_403(user, obj, model):
    if user.is_superuser:
        return

    if _model_has_field(model, "laboratory") and getattr(obj, "laboratory", None):
        ok = UserRole.objects.filter(user=user, laboratory=obj.laboratory).exists()
        if not ok:
            raise PermissionDenied("You do not have access to this laboratory.")


def _log_workflow_event(
    *,
    kind: str,
    object_id: int,
    from_status: str,
    to_status: str,
    user,
    laboratory,
    comment: str = "",
):
    try:
        WorkflowEvent.objects.create(
            kind=kind,
            object_id=object_id,
            from_status=_normalize_status(from_status),
            to_status=_normalize_status(to_status),
            performed_by=user,
            role=None,
            comment=comment or None,
        )
    except Exception:
        return


def _get_state_entered_at(*, kind: str, object_id: int, current_status: str, obj) -> Optional[Any]:
    current_status = _normalize_status(current_status)

    qs = WorkflowEvent.objects.filter(
        kind=kind,
        object_id=object_id,
    ).order_by("-created_at", "-id")

    if current_status:
        e = qs.filter(to_status=current_status).first()
        if e and getattr(e, "created_at", None):
            return e.created_at

    e2 = qs.first()
    if e2 and getattr(e2, "created_at", None):
        return e2.created_at

    for field in ("created_at", "created_on", "created"):
        if hasattr(obj, field):
            v = getattr(obj, field, None)
            if v:
                return v

    return None


def _td_seconds(td: Optional[timedelta]) -> Optional[int]:
    if td is None:
        return None
    try:
        return int(td.total_seconds())
    except Exception:
        return None


def _compute_sla_payload(*, kind: str, status: str, entered_at) -> dict:
    status = _normalize_status(status)
    now = timezone.now()

    sla = get_sla(kind, status) or None
    if not sla or entered_at is None:
        return {
            "applies": False,
            "status": "none",
            "severity": None,
            "entered_at": entered_at,
            "age_seconds": None,
            "warn_after_seconds": None,
            "breach_after_seconds": None,
            "remaining_seconds": None,
        }

    warn_after = sla.get("warn_after")
    breach_after = sla.get("breach_after")

    max_age = sla.get("max_age")
    if breach_after is None and max_age is not None:
        breach_after = max_age

    if warn_after is None and isinstance(breach_after, timedelta):
        warn_after = timedelta(seconds=int(breach_after.total_seconds() * 0.6))

    age = now - entered_at
    age_seconds = _td_seconds(age)
    warn_s = _td_seconds(warn_after)
    breach_s = _td_seconds(breach_after)

    sla_state = "ok"
    if breach_s is not None and age_seconds is not None and age_seconds >= breach_s:
        sla_state = "breached"
    elif warn_s is not None and age_seconds is not None and age_seconds >= warn_s:
        sla_state = "warning"

    remaining_seconds = None
    if breach_s is not None and age_seconds is not None:
        remaining_seconds = breach_s - age_seconds

    return {
        "applies": True,
        "status": sla_state,
        "severity": sla.get("severity"),
        "entered_at": entered_at,
        "age_seconds": age_seconds,
        "warn_after_seconds": warn_s,
        "breach_after_seconds": breach_s,
        "remaining_seconds": remaining_seconds,
    }


# ===============================================================
# Runtime workflow view
# ===============================================================

class WorkflowRuntimeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Workflow runtime state with SLA",
                response=WORKFLOW_RUNTIME_SCHEMA,
            ),
            404: OpenApiResponse(description="Object not found"),
            403: OpenApiResponse(description="Access denied"),
        }
    )
    def get(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)

        try:
            obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        _ensure_laboratory_access_or_403(request.user, obj, model)

        status = _normalize_status(getattr(obj, "status", ""))
        entered_at = _get_state_entered_at(
            kind=kind,
            object_id=obj.pk,
            current_status=status,
            obj=obj,
        )
        sla_payload = _compute_sla_payload(
            kind=kind,
            status=status,
            entered_at=entered_at,
        )

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "status": status,
                "entered_at": entered_at,
                "sla": sla_payload,
            }
        )

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Workflow transition executed",
                response=WORKFLOW_PATCH_SCHEMA,
            ),
            403: OpenApiResponse(description="Missing required role"),
            409: OpenApiResponse(description="Metadata gate blocked"),
        }
    )
    @transaction.atomic
    def patch(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)
        user = request.user

        try:
            obj = model.objects.select_for_update().get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        _ensure_laboratory_access_or_403(user, obj, model)

        current = _normalize_status(getattr(obj, "status", ""))
        target = _get_target_status(request.data)
        if not target:
            raise ValidationError({"status": "Target status is required."})

        comment = _get_comment(request.data)

        required = required_roles(kind, current, target)
        if required:
            user_roles = _get_user_roles(user, getattr(obj, "laboratory", None))
            if not user_roles.intersection(required):
                return Response(
                    {
                        "detail": "Missing required role",
                        "required_roles": sorted(required),
                        "your_roles": sorted(user_roles),
                    },
                    status=403,
                )

        try:
            enforce_metadata_gate(
                laboratory=getattr(obj, "laboratory", None),
                object_type=kind,
                object_id=obj.pk,
            )

            execute_transition(
                instance=obj,
                kind=kind,
                new_status=target,
                user=user,
            )

        except WorkflowBlocked as e:
            return Response(
                {
                    "detail": "Metadata requirements not met",
                    "missing_fields": e.missing_fields,
                    "invalid_fields": e.invalid_fields,
                },
                status=409,
            )

        _log_workflow_event(
            kind=kind,
            object_id=obj.pk,
            from_status=current,
            to_status=target,
            user=user,
            laboratory=getattr(obj, "laboratory", None),
            comment=comment,
        )

        entered_at = _get_state_entered_at(
            kind=kind,
            object_id=obj.pk,
            current_status=target,
            obj=obj,
        )
        sla_payload = _compute_sla_payload(
            kind=kind,
            status=target,
            entered_at=entered_at,
        )

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "from": current,
                "to": target,
                "status": target,
                "entered_at": entered_at,
                "sla": sla_payload,
            }
        )


# ===============================================================
# Workflow timeline view (READ-ONLY)
# ===============================================================

class WorkflowTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Workflow timeline with SLA context",
                response=WORKFLOW_TIMELINE_SCHEMA,
            ),
            404: OpenApiResponse(description="Object not found"),
            403: OpenApiResponse(description="Access denied"),
        }
    )
    def get(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)

        try:
            obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        _ensure_laboratory_access_or_403(request.user, obj, model)

        status = _normalize_status(getattr(obj, "status", ""))

        entered_at = _get_state_entered_at(
            kind=kind,
            object_id=obj.pk,
            current_status=status,
            obj=obj,
        )

        sla_payload = _compute_sla_payload(
            kind=kind,
            status=status,
            entered_at=entered_at,
        )

        events = (
            WorkflowEvent.objects.filter(
                kind=kind,
                object_id=obj.pk,
            )
            .order_by("created_at", "id")
            .values(
                "from_status",
                "to_status",
                "performed_by_id",
                "created_at",
                "comment",
            )
        )

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "status": status,
                "entered_at": entered_at,
                "sla": sla_payload,
                "timeline": list(events),
            }
        )
