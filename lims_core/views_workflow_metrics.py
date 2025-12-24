# lims_core/views_workflow_metrics.py

from datetime import timedelta
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from lims_core.models import WorkflowTransition
from lims_core.workflows.sla import get_sla


class WorkflowMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, kind: str, pk: int):
        transitions = (
            WorkflowTransition.objects
            .filter(kind=kind, object_id=pk)
            .order_by("created_at")
        )

        metrics = []
        prev = None
        current_time = now()

        for t in transitions:
            if prev:
                duration = t.created_at - prev.created_at
                sla = get_sla(kind, prev.to_status)

                metrics.append({
                    "state": prev.to_status,
                    "entered_at": prev.created_at,
                    "exited_at": t.created_at,
                    "duration_seconds": int(duration.total_seconds()),
                    "sla_seconds": int(sla.total_seconds()) if sla else None,
                    "sla_status": (
                        "BREACHED"
                        if sla and duration > sla
                        else "OK"
                        if sla
                        else "N/A"
                    ),
                })

            prev = t

        # Current active state
        if prev:
            duration = current_time - prev.created_at
            sla = get_sla(kind, prev.to_status)

            metrics.append({
                "state": prev.to_status,
                "entered_at": prev.created_at,
                "exited_at": None,
                "duration_seconds": int(duration.total_seconds()),
                "sla_seconds": int(sla.total_seconds()) if sla else None,
                "sla_status": (
                    "BREACHED"
                    if sla and duration > sla
                    else "OK"
                    if sla
                    else "N/A"
                ),
            })

        return Response({
            "kind": kind,
            "object_id": pk,
            "metrics": metrics,
        })
