# lims_core/views_workflows.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from .workflows import workflow_definition, allowed_next_states


class WorkflowDefinitionView(APIView):
    """
    Returns full workflow definition for a given kind.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str):
        try:
            data = workflow_definition(kind)
        except ValueError as e:
            raise ValidationError(str(e))
        return Response(data)


class WorkflowNextStatesView(APIView):
    """
    Returns allowed next states given current state.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str):
        current = request.query_params.get("current")
        if not current:
            raise ValidationError("current query parameter is required.")

        try:
            next_states = allowed_next_states(kind, current)
        except ValueError as e:
            raise ValidationError(str(e))

        return Response(
            {
                "kind": kind,
                "current": current,
                "allowed_next": next_states,
                "terminal": len(next_states) == 0,
            }
        )
