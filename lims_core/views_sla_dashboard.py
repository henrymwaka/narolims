# lims_core/views_sla_dashboard.py
from __future__ import annotations

from typing import Dict, Any

from django.db.models import Count
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from lims_core.models import (
    Laboratory,
    Sample,
    Experiment,
    WorkflowEvent,
)

from lims_core.workflows.sla import get_sla


class SLADashboardView(APIView):
    """
    Aggregated SLA dashboard for a laboratory.

    READ-ONLY.
    No workflow mutation.
    No state transitions.
    Safe for dashboards, reporting, and management oversight.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        lab_id = request.query_params.get("lab")
        if not lab_id:
            raise ValidationError({"lab": "Laboratory id is required"})

        try:
            laboratory = Laboratory.objects.get(pk=lab_id)
        except Laboratory.DoesNotExist:
            return Response({"detail": "Laboratory not found"}, status=404)

        now = timezone.now()

        payload: Dict[str, Any] = {
            "laboratory": {
                "id": laboratory.id,
                "code": laboratory.code,
                "name": laboratory.name,
            },
            "generated_at": now,
            "summary": {},
        }

        for kind, model in {
            "sample": Sample,
            "experiment": Experiment,
        }.items():

            qs = model.objects.filter(laboratory=laboratory)

            total = qs.count()
            ok = warning = breached = none = 0

            # Walk objects once; correctness > micro-optimisation
            for obj in qs:
                status = getattr(obj, "status", None)
                if not status:
                    none += 1
                    continue

                sla = get_sla(kind, status)
                if not sla:
                    none += 1
                    continue

                entered_at = (
                    WorkflowEvent.objects.filter(
                        kind=kind,
                        object_id=obj.pk,
                        to_status=status,
                    )
                    .order_by("-created_at", "-id")
                    .values_list("created_at", flat=True)
                    .first()
                )

                if not entered_at:
                    none += 1
                    continue

                age = now - entered_at

                warn_after = sla.get("warn_after")
                breach_after = sla.get("breach_after") or sla.get("max_age")

                if breach_after and age >= breach_after:
                    breached += 1
                elif warn_after and age >= warn_after:
                    warning += 1
                else:
                    ok += 1

            payload["summary"][kind] = {
                "counts": {
                    "total": total,
                    "ok": ok,
                    "warning": warning,
                    "breached": breached,
                    "none": none,
                }
            }

        return Response(payload)
