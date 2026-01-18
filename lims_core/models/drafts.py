# lims_core/models/drafts.py

from django.conf import settings
from django.db import models
from django.utils import timezone


class ProjectDraft(models.Model):
    """
    Persisted wizard draft for assisted project creation.

    Why persisted:
    - supports "save and resume" across sessions
    - supports audit-friendly "apply" at the end (single commit point)
    - supports non-intimidating UX without hard coding configurations

    payload structure (json):
      {
        "laboratory_id": 1,
        "template": {
          "workflow_code": "DEFAULT",
          "workflow_name": "Default workflow",
          "workflow_version": "v1",
        },
        "project": {
          "name": "My project",
          "description": "...",
        },
        "samples": {
          "create_placeholders": true,
          "count": 24,
          "sample_type": "test"
        }
      }
    """

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPLIED = "applied", "Applied"
        ABANDONED = "abandoned", "Abandoned"

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="project_drafts",
    )

    # Keep a nullable lab pointer so the wizard can start before lab is chosen
    laboratory = models.ForeignKey(
        "lims_core.Laboratory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="project_drafts",
    )

    state = models.CharField(
        max_length=32,
        choices=State.choices,
        default=State.DRAFT,
        db_index=True,
    )

    current_step = models.PositiveSmallIntegerField(default=1, db_index=True)

    payload = models.JSONField(default=dict, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-created_at", "id")

    def mark_submitted(self):
        self.state = self.State.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=["state", "submitted_at", "updated_at"])

    def mark_applied(self):
        self.state = self.State.APPLIED
        self.applied_at = timezone.now()
        self.save(update_fields=["state", "applied_at", "updated_at"])

    def mark_abandoned(self):
        self.state = self.State.ABANDONED
        self.save(update_fields=["state", "updated_at"])
