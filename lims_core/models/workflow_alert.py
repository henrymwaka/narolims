from django.db import models
from django.conf import settings

class WorkflowAlert(models.Model):
    kind = models.CharField(max_length=32)
    object_id = models.PositiveIntegerField()

    state = models.CharField(max_length=32)
    sla_seconds = models.PositiveIntegerField()
    duration_seconds = models.PositiveIntegerField()

    triggered_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        unique_together = ("kind", "object_id", "state")
        ordering = ("-triggered_at",)

    def __str__(self):
        return f"{self.kind}:{self.object_id} {self.state} SLA BREACH"
