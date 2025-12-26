# lims_core/views_workflow_introspection.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from lims_core.models import Sample, Experiment
from lims_core.models.workflow_event import WorkflowEvent
from lims_core.workflows import (
    workflow_definition,
    allowed_transitions,
    normalize_role,
)
from lims_core.views import require_laboratory


MODEL_REGISTRY = {
    "sample": Sample,
    "experiment": Experiment,
}


class WorkflowDefinitionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str):
        try:
            return Response(workflow_definition(kind))
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class WorkflowAllowedTransitionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str, object_id: int):
        kind = (kind or "").strip().lower()
        Model = MODEL_REGISTRY.get(kind)

        if not Model:
            return Response(
                {"detail": "Unsupported workflow kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lab = require_laboratory(request)

        try:
            obj = Model.objects.get(pk=object_id, laboratory=lab)
        except Model.DoesNotExist:
            return Response(
                {"detail": "Object not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        role = (
            request.user.userrole_set
            .filter(laboratory=lab)
            .values_list("role", flat=True)
            .first()
        )

        role = normalize_role(role)

        transitions = allowed_transitions(
            kind=kind,
            current=obj.status,
            role=role,
        )

        return Response(
            {
                "object_id": obj.pk,
                "kind": kind,
                "current_status": obj.status,
                "allowed_transitions": transitions,
            }
        )


class WorkflowHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str, object_id: int):
        kind = (kind or "").strip().lower()

        if kind not in MODEL_REGISTRY:
            return Response(
                {"detail": "Unsupported workflow kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lab = require_laboratory(request)

        qs = WorkflowEvent.objects.filter(
            kind=kind,
            object_id=object_id,
        ).order_by("created_at")

        data = [
            {
                "from": ev.from_status,
                "to": ev.to_status,
                "role": ev.role,
                "performed_by": ev.performed_by.username,
                "comment": ev.comment,
                "at": ev.created_at,
            }
            for ev in qs
        ]

        return Response(
            {
                "kind": kind,
                "object_id": object_id,
                "history": data,
            }
        )
