# lims_core/models/drafts.py

from django.conf import settings
from django.db import models
from django.utils import timezone


class ProjectDraft(models.Model):
    """
    Persisted wizard draft for assisted project creation.

    payload structure (json):
      {
        "laboratory_id": 1,
        "template": {...},
        "project": {...},
        "samples": {...}
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


class LabConfigDraft(models.Model):
    """
    Persisted wizard draft for laboratory configuration.

    payload structure (json):
      {
        "laboratory_id": 1,
        "profile": {
          "lab_type": "soils",
          "description": "...",
          "accreditation_mode": false,
          "schema_code": "INTAKE_CORE",
          "schema_version": "v1",
          "default_analysis_context_id": ""
        },
        "assignments": [
          {"pack_id": 12, "is_enabled": true, "priority": 10},
          {"pack_id": 17, "is_enabled": false, "priority": 0}
        ]
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
        related_name="labconfig_drafts",
    )

    laboratory = models.ForeignKey(
        "lims_core.Laboratory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="labconfig_drafts",
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
