from django.db import models
from django.contrib.auth.models import User


class WorkflowEvent(models.Model):
    """
    Immutable audit log for workflow transitions.
    """

    KIND_CHOICES = (
        ("sample", "Sample"),
        ("experiment", "Experiment"),
    )

    kind = models.CharField(max_length=32, choices=KIND_CHOICES)

    object_id = models.PositiveIntegerField()
    from_status = models.CharField(max_length=64)
    to_status = models.CharField(max_length=64)

    performed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="workflow_events",
    )

    role = models.CharField(max_length=64)

    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "object_id"]),
        ]

    def __str__(self):
        return (
            f"{self.kind.upper()} {self.object_id}: "
            f"{self.from_status} → {self.to_status} "
            f"by {self.performed_by.username}"
        )
