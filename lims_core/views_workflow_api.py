# lims_core/views_workflow_api.py

from __future__ import annotations

from typing import Dict, Set, Type

from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError, NotAuthenticated

from lims_core.models import Sample, Experiment, UserRole
from lims_core.workflows import allowed_transitions
from lims_core.workflows.executor import execute_transition


# =============================================================
# Workflow model registry
# =============================================================

KIND_MODEL_MAP: Dict[str, Type] = {
    "sample": Sample,
    "experiment": Experiment,
}


# =============================================================
# Helpers
# =============================================================

def _normalize_kind(kind: str) -> str:
    kind = (kind or "").strip().lower()
    if kind not in KIND_MODEL_MAP:
        raise ValidationError(
            {"kind": "Invalid workflow kind. Use 'sample' or 'experiment'."}
        )
    return kind


def _require_auth(user) -> None:
    """
    Enforce authentication in a way that returns DRF's normal 401/403
    instead of Django login redirects (302) under session-based setups.
    """
    if not user or not getattr(user, "is_authenticated", False):
        raise NotAuthenticated("Authentication credentials were not provided.")


def _get_user_roles_for_instance(user, instance) -> Set[str]:
    """
    Returns the set of roles a user has in the laboratory context
    of the given instance.

    Superusers are treated as ADMIN.
    """
    _require_auth(user)

    if getattr(user, "is_superuser", False):
        return {"ADMIN"}

    lab_id = getattr(instance, "laboratory_id", None)
    qs = UserRole.objects.filter(user=user)

    if lab_id:
        qs = qs.filter(laboratory_id=lab_id)

    return set(qs.values_list("role", flat=True))


def _allowed_for_roles(kind: str, current: str, roles: Set[str]) -> list[str]:
    """
    Union allowed transitions across all roles the user holds.
    """
    out: Set[str] = set()
    current = (current or "").strip().upper()

    for role in roles:
        out |= set(allowed_transitions(kind, current, role))

    return sorted(out)


# =============================================================
# API: Allowed transitions
# =============================================================

class WorkflowAllowedView(APIView):
    """
    GET /lims/workflows/<kind>/<pk>/allowed/

    Returns:
    - current state
    - allowed next states (role-aware)
    - user roles considered
    """
    # IMPORTANT:
    # We keep AllowAny here and enforce auth explicitly to avoid 302 redirects
    # in environments where unauthenticated requests get redirected to login.
    permission_classes = [AllowAny]

    def get(self, request, kind: str, pk: int):
        kind = _normalize_kind(kind)
        model = KIND_MODEL_MAP[kind]

        instance = get_object_or_404(model, pk=pk)

        current = getattr(instance, "status", None)
        roles = _get_user_roles_for_instance(request.user, instance)
        allowed = _allowed_for_roles(kind, current, roles)

        return Response(
            {
                "kind": kind,
                "object_id": instance.pk,
                "current": current,
                "allowed": allowed,
                "roles": sorted(roles),
            }
        )


# =============================================================
# API: Execute workflow transition (AUTHORITATIVE)
# =============================================================

class WorkflowTransitionView(APIView):
    """
    POST /lims/workflows/<kind>/<pk>/transition/

    Body:
        { "to_status": "QC_PASSED" }
        or
        { "status": "QC_PASSED" }

    This endpoint is the ONLY API-level entry point
    that mutates workflow state.
    """
    # Same reasoning as above: avoid 302 redirects, raise DRF 401 instead.
    permission_classes = [AllowAny]

    def post(self, request, kind: str, pk: int):
        _require_auth(request.user)

        kind = _normalize_kind(kind)
        model = KIND_MODEL_MAP[kind]

        instance = get_object_or_404(model, pk=pk)

        payload = request.data or {}
        to_status = payload.get("to_status") or payload.get("status")

        if not to_status:
            raise ValidationError({"to_status": "This field is required."})

        # -----------------------------------------------------
        # Authoritative transition execution
        # -----------------------------------------------------
        execute_transition(
            instance=instance,
            kind=kind,
            new_status=str(to_status),
            user=request.user,
        )

        instance.refresh_from_db()

        return Response(
            {
                "kind": kind,
                "object_id": instance.pk,
                "current": instance.status,
            }
        )
