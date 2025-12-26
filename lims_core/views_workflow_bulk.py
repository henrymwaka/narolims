# lims_core/views_workflow_bulk.py
from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ObjectDoesNotExist, FieldDoesNotExist
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from drf_spectacular.utils import extend_schema

from lims_core.models import Sample, Experiment, UserRole, WorkflowEvent
from lims_core.workflows import required_roles
from lims_core.workflows.executor import execute_transition

logger = logging.getLogger(__name__)


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
        UserRole.objects.filter(user=user, laboratory=laboratory)
        .values_list("role", flat=True)
    )


def _pick_role_for_event(user, laboratory) -> str:
    if user.is_superuser:
        return "ADMIN"
    roles = sorted(_get_user_roles(user, laboratory))
    return roles[0] if roles else "USER"


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
    """
    Audit logging must never break workflow execution.
    """
    try:
        WorkflowEvent.objects.create(
            kind=kind,
            object_id=object_id,
            from_status=_normalize_status(from_status),
            to_status=_normalize_status(to_status),
            performed_by=user,
            role=_pick_role_for_event(user, laboratory),
            comment=comment or "",
        )
    except Exception:
        logger.exception("WorkflowEvent logging failed (ignored).")
        return


# ===============================================================
# Bulk transition endpoint (public URL hits this one)
# ===============================================================

class WorkflowBulkTransitionView(APIView):
    """
    POST → execute a bulk workflow transition

    Expected payload:
      {
        "kind":"sample",
        "target_status":"IN_PROCESS",
        "object_ids":[3,4,5],
        "comment":"bulk start"
      }

    Behavior:
    - Never returns HTTP 500 for normal workflow rule failures.
    - If current status already equals target status, it is treated as a skipped success.
    - Per-object outcomes are returned in "results".
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Workflows"])
    @transaction.atomic
    def post(self, request, kind: str):
        model = _get_model_for_kind(kind)

        data = request.data if isinstance(request.data, dict) else {}

        body_kind = (data.get("kind") or "").strip().lower()
        if body_kind and body_kind != (kind or "").strip().lower():
            raise ValidationError({"kind": "Kind in payload does not match URL kind."})

        target = _normalize_status(data.get("target_status"))
        if not target:
            raise ValidationError({"target_status": "Target status is required."})

        object_ids = data.get("object_ids", [])
        if not isinstance(object_ids, list) or not object_ids:
            raise ValidationError({"object_ids": "Provide a non-empty list of IDs."})

        comment = _get_comment(data)

        results = []
        for oid in object_ids:
            try:
                oid_int = int(oid)
            except Exception:
                results.append({"object_id": oid, "ok": False, "error": "Invalid object_id"})
                continue

            try:
                obj = model.objects.select_for_update().get(pk=oid_int)
            except ObjectDoesNotExist:
                results.append({"object_id": oid_int, "ok": False, "error": "Not found"})
                continue

            try:
                _ensure_laboratory_access_or_403(request.user, obj, model)
            except PermissionDenied as e:
                results.append({"object_id": oid_int, "ok": False, "error": str(e)})
                continue

            current = _normalize_status(getattr(obj, "status", ""))

            # No-op transitions should not 500
            if current == target:
                results.append(
                    {
                        "object_id": oid_int,
                        "ok": True,
                        "skipped": True,
                        "from": current,
                        "to": target,
                        "note": "Already in target status",
                    }
                )
                continue

            required = required_roles(kind, current, target)
            if required:
                user_roles = _get_user_roles(request.user, getattr(obj, "laboratory", None))
                if not user_roles.intersection(required):
                    results.append(
                        {
                            "object_id": oid_int,
                            "ok": False,
                            "error": "Missing required role",
                            "required_roles": sorted(required),
                            "your_roles": sorted(user_roles),
                        }
                    )
                    continue

            try:
                execute_transition(
                    instance=obj,
                    kind=kind,
                    new_status=target,
                    user=request.user,
                )
            except PermissionDenied as e:
                results.append({"object_id": oid_int, "ok": False, "error": str(e)})
                continue
            except ValidationError as e:
                # This is a normal workflow rule failure, never a 500
                results.append({"object_id": oid_int, "ok": False, "error": e.detail})
                continue
            except Exception as e:
                # True unexpected errors get captured per-object, not as a whole-request 500
                logger.exception("Unexpected bulk workflow error for %s/%s", kind, oid_int)
                results.append({"object_id": oid_int, "ok": False, "error": f"Unexpected error: {e.__class__.__name__}"})
                continue

            _log_workflow_event(
                kind=kind,
                object_id=obj.pk,
                from_status=current,
                to_status=target,
                user=request.user,
                laboratory=getattr(obj, "laboratory", None),
                comment=comment,
            )

            results.append({"object_id": oid_int, "ok": True, "from": current, "to": target})

        return Response(
            {
                "kind": kind,
                "target_status": target,
                "count": len(object_ids),
                "ok_count": sum(1 for r in results if r.get("ok")),
                "skipped_count": sum(1 for r in results if r.get("skipped")),
                "results": results,
            }
        )
