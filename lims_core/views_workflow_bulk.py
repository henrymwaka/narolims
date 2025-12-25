from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from lims_core.models import Sample, Experiment
from lims_core.services.workflow_bulk import bulk_transition
from lims_core.views import require_laboratory


class WorkflowBulkTransitionView(APIView):
    """
    Canonical API endpoint for bulk workflow transitions.

    This view:
    - Resolves laboratory context
    - Resolves user role within laboratory
    - Dispatches to the single authoritative bulk workflow engine
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        kind = request.data.get("kind")
        target_status = request.data.get("target_status")
        object_ids = request.data.get("object_ids", [])
        comment = request.data.get("comment", "")

        # ---------------------------------------------------------
        # 1. Basic request validation
        # ---------------------------------------------------------
        if not kind or not target_status or not object_ids:
            return Response(
                {
                    "detail": (
                        "kind, target_status, and object_ids "
                        "are required fields"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 2. Resolve laboratory + actor role
        # ---------------------------------------------------------
        laboratory = require_laboratory(request)
        user = request.user

        user_role = (
            user.userrole_set.filter(laboratory=laboratory)
            .values_list("role", flat=True)
            .first()
        )

        if not user_role:
            return Response(
                {"detail": "User has no role in this laboratory"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---------------------------------------------------------
        # 3. Load objects by workflow kind
        # ---------------------------------------------------------
        kind = kind.strip().lower()

        if kind == "sample":
            objects = list(
                Sample.objects.filter(
                    id__in=object_ids,
                    laboratory=laboratory,
                )
            )
        elif kind == "experiment":
            objects = list(
                Experiment.objects.filter(
                    id__in=object_ids,
                    laboratory=laboratory,
                )
            )
        else:
            return Response(
                {"detail": f"Unsupported workflow kind: {kind}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 4. Execute bulk workflow transition
        # ---------------------------------------------------------
        result = bulk_transition(
            kind=kind,
            objects=objects,
            target_status=target_status,
            actor=user,
            actor_role=user_role,
            comment=comment,
        )

        return Response(result, status=status.HTTP_200_OK)
