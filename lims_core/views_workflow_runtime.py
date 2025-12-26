# lims_core/views_workflow_runtime.py
from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist, FieldDoesNotExist
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from drf_spectacular.utils import extend_schema

from lims_core.models import (
    Sample,
    Experiment,
    UserRole,
    WorkflowEvent,
)
from lims_core.workflows import (
    allowed_next_states,
    required_roles,
)
from lims_core.workflows.executor import execute_transition


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
    """
    Returns role codes the user has in the given laboratory.
    """
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
    """
    Enforces per-lab access if the model has a laboratory field.
    """
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
    Audit logging should never break workflows.
    If the model constraints reject role/comment, fail silently.
    """
    try:
        WorkflowEvent.objects.create(
            kind=kind,
            object_id=object_id,
            from_status=_normalize_status(from_status),
            to_status=_normalize_status(to_status),
            performed_by=user,
            role=None,          # keep safe (your DB currently stores null)
            comment=comment or None,
        )
    except Exception:
        return


def _safe_err(e: Exception) -> dict:
    return {"type": e.__class__.__name__, "message": str(e)}


# ===============================================================
# Runtime workflow view
# ===============================================================

class WorkflowRuntimeView(APIView):
    """
    GET   → read current workflow state
    PATCH → execute workflow transition (authoritative path)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)

        try:
            obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        try:
            _ensure_laboratory_access_or_403(request.user, obj, model)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "status": _normalize_status(getattr(obj, "status", "")),
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

        try:
            _ensure_laboratory_access_or_403(user, obj, model)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)

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
                        "detail": "You do not have the required role to perform this transition.",
                        "required_roles": sorted(required),
                        "your_roles": sorted(user_roles),
                    },
                    status=403,
                )

        try:
            execute_transition(instance=obj, kind=kind, new_status=target, user=user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        except ValidationError as e:
            return Response({"detail": e.detail}, status=409)

        _log_workflow_event(
            kind=kind,
            object_id=obj.pk,
            from_status=current,
            to_status=target,
            user=user,
            laboratory=getattr(obj, "laboratory", None),
            comment=comment,
        )

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "from": current,
                "to": target,
                "status": target,
            }
        )


# ===============================================================
# POST transition endpoint (matches /lims/workflows/<kind>/<pk>/transition/)
# ===============================================================

class WorkflowTransitionView(APIView):
    """
    POST → execute a single workflow transition

    Payload:
      {"to":"ARCHIVED","comment":"..."}  OR  {"status":"ARCHIVED","comment":"..."}
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Workflows"])
    @transaction.atomic
    def post(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)
        user = request.user

        try:
            obj = model.objects.select_for_update().get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        try:
            _ensure_laboratory_access_or_403(user, obj, model)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)

        current = _normalize_status(getattr(obj, "status", ""))

        target = _get_target_status(request.data)
        if not target:
            raise ValidationError({"to": "Target status is required."})

        comment = _get_comment(request.data)

        required = required_roles(kind, current, target)
        if required:
            user_roles = _get_user_roles(user, getattr(obj, "laboratory", None))
            if not user_roles.intersection(required):
                return Response(
                    {
                        "detail": "You do not have the required role to perform this transition.",
                        "required_roles": sorted(required),
                        "your_roles": sorted(user_roles),
                    },
                    status=403,
                )

        try:
            execute_transition(instance=obj, kind=kind, new_status=target, user=user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        except ValidationError as e:
            # Your existing behavior returns 400 with a single message, keep it simple
            return Response({"status": str(e.detail)}, status=400)
        except Exception as e:
            return Response({"detail": "Transition failed", "error": _safe_err(e)}, status=500)

        _log_workflow_event(
            kind=kind,
            object_id=obj.pk,
            from_status=current,
            to_status=target,
            user=user,
            laboratory=getattr(obj, "laboratory", None),
            comment=comment,
        )

        return Response({"kind": kind, "object_id": obj.pk, "current": target})


# ===============================================================
# Bulk transition endpoint (matches /lims/workflows/<kind>/bulk/)
# ===============================================================

class WorkflowBulkTransitionView(APIView):
    """
    POST → execute a bulk workflow transition

    Payload:
      {
        "kind":"sample",
        "target_status":"IN_PROCESS",
        "object_ids":[3,4,5],
        "comment":"bulk start"
      }
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Workflows"])
    @transaction.atomic
    def post(self, request, kind: str):
        try:
            model = _get_model_for_kind(kind)

            data = request.data if isinstance(request.data, dict) else {}
            body_kind = (data.get("kind") or "").strip().lower()
            if body_kind and body_kind != kind:
                raise ValidationError({"kind": "Kind in payload does not match URL kind."})

            target = _normalize_status(data.get("target_status"))
            if not target:
                raise ValidationError({"target_status": "Target status is required."})

            object_ids = data.get("object_ids", [])
            if not isinstance(object_ids, list) or not object_ids:
                raise ValidationError({"object_ids": "Provide a non-empty list of IDs."})

            comment = _get_comment(data)

            results: list[dict] = []
            for oid in object_ids:
                # Always isolate each object; never crash entire bulk request
                try:
                    oid_int = int(oid)
                except Exception:
                    results.append({"object_id": oid, "ok": False, "error": {"type": "ValueError", "message": "Invalid object_id"}})
                    continue

                try:
                    obj = model.objects.select_for_update().get(pk=oid_int)
                except ObjectDoesNotExist:
                    results.append({"object_id": oid_int, "ok": False, "error": {"type": "NotFound", "message": "Not found"}})
                    continue

                try:
                    _ensure_laboratory_access_or_403(request.user, obj, model)
                except PermissionDenied as e:
                    results.append({"object_id": oid_int, "ok": False, "error": _safe_err(e)})
                    continue

                current = _normalize_status(getattr(obj, "status", ""))

                required = required_roles(kind, current, target)
                if required:
                    user_roles = _get_user_roles(request.user, getattr(obj, "laboratory", None))
                    if not user_roles.intersection(required):
                        results.append(
                            {
                                "object_id": oid_int,
                                "ok": False,
                                "error": {"type": "PermissionDenied", "message": "Missing required role"},
                                "required_roles": sorted(required),
                                "your_roles": sorted(user_roles),
                            }
                        )
                        continue

                try:
                    execute_transition(instance=obj, kind=kind, new_status=target, user=request.user)
                except PermissionDenied as e:
                    results.append({"object_id": oid_int, "ok": False, "error": _safe_err(e)})
                    continue
                except ValidationError as e:
                    results.append({"object_id": oid_int, "ok": False, "error": {"type": "ValidationError", "message": str(e.detail), "detail": e.detail}})
                    continue
                except Exception as e:
                    # This is the important one: stop the hidden HTML 500
                    results.append({"object_id": oid_int, "ok": False, "error": _safe_err(e)})
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
                    "results": results,
                }
            )

        except ValidationError as e:
            return Response({"detail": e.detail}, status=400)
        except Exception as e:
            return Response({"detail": "Bulk transition failed", "error": _safe_err(e)}, status=500)


# ===============================================================
# Allowed transitions
# ===============================================================

class WorkflowAllowedTransitionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)

        try:
            obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        try:
            _ensure_laboratory_access_or_403(request.user, obj, model)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)

        current = _normalize_status(getattr(obj, "status", ""))
        all_allowed = allowed_next_states(kind, current) or []

        user_roles = _get_user_roles(request.user, getattr(obj, "laboratory", None))

        visible = []
        for target in all_allowed:
            required = required_roles(kind, current, target)
            if not required or user_roles.intersection(required):
                visible.append(target)

        return Response(
            {
                "kind": kind,
                "object_id": obj.pk,
                "current": current,
                "allowed": sorted(visible),
                "roles": sorted(user_roles),
            }
        )


# ===============================================================
# Workflow timeline
# ===============================================================

class WorkflowTimelineView(APIView):
    """
    Read-only workflow transition timeline (WorkflowEvent-based).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Workflows"])
    def get(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)

        try:
            obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        try:
            _ensure_laboratory_access_or_403(request.user, obj, model)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)

        qs = (
            WorkflowEvent.objects.filter(kind=kind, object_id=obj.pk)
            .select_related("performed_by")
            .order_by("created_at", "id")
        )

        timeline = [
            {
                "id": e.id,
                "source": "transition",
                "at": e.created_at,
                "user": e.performed_by.username if e.performed_by else None,
                "role": e.role,
                "from": e.from_status,
                "to": e.to_status,
                "comment": e.comment,
            }
            for e in qs
        ]

        return Response(
            {
                "kind": kind,
                "object_id": obj.pk,
                "current": _normalize_status(getattr(obj, "status", "")),
                "timeline": timeline,
            }
        )
