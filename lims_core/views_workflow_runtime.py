# lims_core/views_workflow_runtime.py
from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist, FieldDoesNotExist

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from drf_spectacular.utils import extend_schema

from lims_core.models import Sample, Experiment, UserRole
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


def _get_target_status(data):
    if not isinstance(data, dict):
        return None
    if "status" in data:
        return str(data["status"]).strip().upper()
    if "to" in data:
        return str(data["to"]).strip().upper()
    return None


def _get_user_roles(user, laboratory) -> set[str]:
    """
    Returns role codes the user has in the given laboratory.
    """
    if user.is_superuser:
        return {"ADMIN"}

    return set(
        UserRole.objects.filter(
            user=user,
            laboratory=laboratory,
        ).values_list("role", flat=True)
    )


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

        # Laboratory access control
        if (
            _model_has_field(model, "laboratory")
            and obj.laboratory
            and not request.user.is_superuser
        ):
            if not UserRole.objects.filter(
                user=request.user,
                laboratory=obj.laboratory,
            ).exists():
                return Response(
                    {"detail": "You do not have access to this laboratory."},
                    status=403,
                )

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "status": obj.status,
            }
        )

    def patch(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)
        user = request.user

        try:
            obj = model.objects.select_for_update().get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        # -------------------------------------------------------
        # Laboratory access control
        # -------------------------------------------------------
        if (
            _model_has_field(model, "laboratory")
            and obj.laboratory
            and not user.is_superuser
        ):
            if not UserRole.objects.filter(
                user=user,
                laboratory=obj.laboratory,
            ).exists():
                return Response(
                    {"detail": "You do not have access to this laboratory."},
                    status=403,
                )

        current = (obj.status or "").strip().upper()

        # -------------------------------------------------------
        # Transition request
        # -------------------------------------------------------
        target = _get_target_status(request.data)
        if not target:
            raise ValidationError({"status": "Target status is required."})

        # -------------------------------------------------------
        # UX-level role visibility check
        # (executor remains authoritative)
        # -------------------------------------------------------
        required = required_roles(kind, current, target)
        if required:
            user_roles = _get_user_roles(user, obj.laboratory)
            if not user_roles.intersection(required):
                return Response(
                    {
                        "detail": "You do not have the required role to perform this transition.",
                        "required_roles": sorted(required),
                        "your_roles": sorted(user_roles),
                    },
                    status=403,
                )

        # -------------------------------------------------------
        # EXECUTE TRANSITION (single authoritative path)
        # -------------------------------------------------------
        try:
            execute_transition(
                instance=obj,
                kind=kind,
                new_status=target,
                user=user,
            )
        except PermissionDenied as e:
            # Role or access violation
            return Response({"detail": str(e)}, status=403)
        except ValidationError as e:
            # State conflict (terminal / illegal transition)
            return Response(
                {"detail": e.detail},
                status=409,
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

        current = (obj.status or "").strip().upper()
        all_allowed = allowed_next_states(kind, current)

        if not all_allowed:
            return Response(
                {
                    "id": obj.pk,
                    "kind": kind,
                    "current": current,
                    "allowed": [],
                }
            )

        user_roles = _get_user_roles(request.user, obj.laboratory)

        visible = []
        for target in all_allowed:
            required = required_roles(kind, current, target)
            if not required or user_roles.intersection(required):
                visible.append(target)

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "current": current,
                "allowed": sorted(visible),
            }
        )


# ===============================================================
# Workflow timeline
# ===============================================================

class WorkflowTimelineView(APIView):
    """
    Read-only workflow transition timeline.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Workflows"])
    def get(self, request, kind: str, pk: int):
        model = _get_model_for_kind(kind)

        try:
            obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if (
            _model_has_field(model, "laboratory")
            and obj.laboratory
            and not request.user.is_superuser
        ):
            if not UserRole.objects.filter(
                user=request.user,
                laboratory=obj.laboratory,
            ).exists():
                return Response(
                    {"detail": "You do not have access to this laboratory."},
                    status=403,
                )

        transitions = (
            obj.workflow_transitions
            .select_related("performed_by")
            .order_by("created_at", "id")
        )

        timeline = [
            {
                "at": t.created_at,
                "user": t.performed_by.username if t.performed_by else None,
                "from": t.from_status,
                "to": t.to_status,
            }
            for t in transitions
        ]

        return Response(
            {
                "id": obj.pk,
                "kind": kind,
                "timeline": timeline,
            }
        )
