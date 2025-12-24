# lims_core/views_workflow_api.py
from __future__ import annotations

from typing import Dict, Set, Type

from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from lims_core.models import Sample, Experiment, UserRole
from lims_core.workflows import allowed_transitions
from lims_core.services.workflow_service import perform_workflow_transition


KIND_MODEL_MAP: Dict[str, Type] = {
    "sample": Sample,
    "experiment": Experiment,
}


def _normalize_kind(kind: str) -> str:
    kind = (kind or "").strip().lower()
    if kind not in KIND_MODEL_MAP:
        raise ValidationError({"kind": "Invalid workflow kind. Use sample or experiment."})
    return kind


def _get_user_roles_for_instance(user, instance) -> Set[str]:
    """
    Returns a set of roles for this user in the instance's lab context.
    Superuser is treated as ADMIN.
    """
    if not user or not user.is_authenticated:
        return set()

    if getattr(user, "is_superuser", False):
        return {"ADMIN"}

    lab_id = getattr(instance, "laboratory_id", None)
    qs = UserRole.objects.filter(user=user)

    if lab_id:
        qs = qs.filter(laboratory_id=lab_id)

    return set(qs.values_list("role", flat=True))


def _allowed_for_roles(kind: str, current: str, roles: Set[str]) -> list[str]:
    """
    allowed_transitions() expects a single role.
    Users can have multiple roles, so we union them.
    """
    out: Set[str] = set()
    for r in roles:
        out |= set(allowed_transitions(kind, current, r))
    return sorted(out)


class WorkflowAllowedView(APIView):
    """
    GET /lims/workflows/<kind>/<pk>/allowed/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str, pk: int):
        kind = _normalize_kind(kind)
        model = KIND_MODEL_MAP[kind]

        instance = get_object_or_404(model, pk=pk)

        roles = _get_user_roles_for_instance(request.user, instance)
        allowed = _allowed_for_roles(kind, getattr(instance, "status", ""), roles)

        return Response(
            {
                "kind": kind,
                "object_id": instance.pk,
                "current": getattr(instance, "status", None),
                "allowed": allowed,
                "roles": sorted(roles),
            }
        )


class WorkflowTransitionView(APIView):
    """
    POST /lims/workflows/<kind>/<pk>/transition/
    Body: { "to_status": "QC_PASSED" } or { "status": "QC_PASSED" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, kind: str, pk: int):
        kind = _normalize_kind(kind)
        model = KIND_MODEL_MAP[kind]

        instance = get_object_or_404(model, pk=pk)

        payload = request.data or {}
        to_status = payload.get("to_status") or payload.get("status")
        if not to_status:
            raise ValidationError({"to_status": "This field is required."})

        updated = perform_workflow_transition(
            instance=instance,
            kind=kind,
            new_status=str(to_status),
            user=request.user,
        )

        return Response(
            {
                "kind": kind,
                "object_id": updated.pk,
                "from_status": payload.get("from_status") or None,
                "current": updated.status,
            }
        )
