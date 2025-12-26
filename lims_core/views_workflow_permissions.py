# lims_core/views_workflow_permissions.py

from typing import List

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from lims_core.models import Sample, Experiment, UserRole
from lims_core.views import require_laboratory
from lims_core.workflows import (
    allowed_transitions,
    allowed_next_states,
    normalize_role,
)

MODEL_REGISTRY = {
    "sample": Sample,
    "experiment": Experiment,
}


class WorkflowPermissionMatrixView(APIView):
    """
    Read-only endpoint that returns workflow permissions
    for a user across multiple objects.

    NO side effects.
    NO transitions.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str):
        kind = (kind or "").strip().lower()

        if kind not in MODEL_REGISTRY:
            return Response(
                {"detail": "Unsupported workflow kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_ids = request.query_params.get("object_ids", "")
        if not raw_ids:
            return Response(
                {"detail": "object_ids query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            object_ids = [int(x) for x in raw_ids.split(",") if x.strip()]
        except ValueError:
            return Response(
                {"detail": "object_ids must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lab = require_laboratory(request)
        user = request.user

        # Resolve user roles (lab-scoped)
        if user.is_superuser:
            user_roles = {"ADMIN"}
        else:
            roles = UserRole.objects.filter(
                user=user,
                laboratory=lab,
            ).values_list("role", flat=True)
            user_roles = {normalize_role(r) for r in roles}

        Model = MODEL_REGISTRY[kind]
        qs = Model.objects.filter(id__in=object_ids, laboratory=lab)

        results: List[dict] = []

        for obj in qs:
            current = (obj.status or "").strip().upper()

            next_states = allowed_next_states(kind, current)

            if not next_states:
                results.append(
                    {
                        "id": obj.id,
                        "current_status": current,
                        "allowed_transitions": [],
                        "terminal": True,
                        "blocked_reason": "Terminal state",
                    }
                )
                continue

            allowed = set()
            for role in user_roles:
                allowed.update(
                    allowed_transitions(kind, current, role)
                )

            if not allowed:
                results.append(
                    {
                        "id": obj.id,
                        "current_status": current,
                        "allowed_transitions": [],
                        "terminal": False,
                        "blocked_reason": "Role not permitted",
                    }
                )
            else:
                results.append(
                    {
                        "id": obj.id,
                        "current_status": current,
                        "allowed_transitions": sorted(allowed),
                        "terminal": False,
                    }
                )

        return Response(
            {
                "kind": kind,
                "actor": user.username,
                "roles": sorted(user_roles),
                "objects": results,
            },
            status=status.HTTP_200_OK,
        )
