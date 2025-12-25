# lims_core/models_workflow_alerts.py
from __future__ import annotations

from django.conf import settings
from django.db import models


class WorkflowSlaBreach(models.Model):
    """
    Derived, write-once record created by the SLA scanner.
    This is not the ground truth of workflow history. WorkflowTransition is.
    """

    kind = models.CharField(max_length=32)          # "sample" | "experiment"
    object_id = models.PositiveIntegerField()

    status = models.CharField(max_length=64)        # status at time of breach
    threshold_hours = models.PositiveIntegerField() # SLA threshold used

    started_at = models.DateTimeField()             # when this status window began
    breached_at = models.DateTimeField(auto_now_add=True)

    laboratory = models.ForeignKey(
        "lims_core.Laboratory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sla_breaches",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sla_breaches_created",
    )

    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["kind", "object_id"]),
            models.Index(fields=["laboratory", "breached_at"]),
            models.Index(fields=["kind", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "object_id", "status", "started_at", "threshold_hours"],
                name="uniq_sla_breach_window",
            )
        ]

    def __str__(self) -> str:
        return f"SLA breach {self.kind}:{self.object_id} {self.status}"
