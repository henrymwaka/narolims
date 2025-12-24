# lims_core/views_workflow_bulk.py
from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist, FieldDoesNotExist
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

from lims_core.models import Sample, Experiment, UserRole
from lims_core.workflows.executor import execute_transition


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


def _has_lab_access(user, obj) -> bool:
    if user.is_superuser:
        return True

    lab = getattr(obj, "laboratory", None)
    if not lab:
        return True

    return UserRole.objects.filter(user=user, laboratory=lab).exists()


class WorkflowBulkTransitionView(APIView):
    """
    POST bulk transitions.

    Payload:
    {
      "items": [
        {"id": 1, "status": "QC_PASSED", "note": "ok"},
        {"id": 2, "to": "QC_FAILED"}
      ],
      "atomic": false
    }

    Response includes per-item success/failure.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, kind: str):
        model = _get_model_for_kind(kind)
        user = request.user

        data = request.data or {}
        items = data.get("items", None)
        atomic = bool(data.get("atomic", False))

        if not isinstance(items, list) or not items:
            raise ValidationError({"items": "Provide a non-empty list of items."})

        # Normalize targets early
        normalized = []
        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                raise ValidationError({"items": f"Item {idx} must be an object."})

            obj_id = it.get("id")
            if not obj_id:
                raise ValidationError({"items": f"Item {idx} missing 'id'."})

            target = it.get("status") or it.get("to")
            if not target:
                raise ValidationError({"items": f"Item {idx} missing 'status' or 'to'."})

            normalized.append(
                {
                    "id": int(obj_id),
                    "target": str(target).strip().upper(),
                    "note": (it.get("note") or "").strip() or None,
                }
            )

        results = []

        def _run_one(entry):
            try:
                obj = model.objects.select_for_update().get(pk=entry["id"])
            except ObjectDoesNotExist:
                return {
                    "id": entry["id"],
                    "ok": False,
                    "error": "Not found.",
                }

            if not _has_lab_access(user, obj):
                return {
                    "id": entry["id"],
                    "ok": False,
                    "error": "You do not have access to this laboratory.",
                }

            try:
                old = (obj.status or "").strip().upper()
                execute_transition(
                    instance=obj,
                    kind=kind,
                    new_status=entry["target"],
                    user=user,
                    note=entry["note"],
                )
                return {
                    "id": obj.pk,
                    "ok": True,
                    "from": old,
                    "to": entry["target"],
                    "status": entry["target"],
                }
            except (DRFPermissionDenied, Exception) as e:
                # DRFPermissionDenied rarely raised here, but keep it safe
                return {
                    "id": entry["id"],
                    "ok": False,
                    "error": str(e),
                }

        if atomic:
            # all-or-nothing
            with transaction.atomic():
                for entry in normalized:
                    out = _run_one(entry)
                    results.append(out)
                    if not out["ok"]:
                        # rollback everything
                        raise ValidationError(
                            {
                                "detail": "Atomic bulk transition failed; rolled back.",
                                "first_error": out,
                            }
                        )
        else:
            # best-effort
            for entry in normalized:
                with transaction.atomic():
                    results.append(_run_one(entry))

        ok_count = sum(1 for r in results if r.get("ok"))
        return Response(
            {
                "kind": kind,
                "atomic": atomic,
                "requested": len(results),
                "succeeded": ok_count,
                "failed": len(results) - ok_count,
                "results": results,
            }
        )
