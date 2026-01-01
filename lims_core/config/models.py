from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from lims_core.labs.models import LaboratoryProfile
from lims_core.metadata.models import MetadataSchema


class ConfigPack(models.Model):
    KIND_SCHEMA = "schema"
    KIND_WORKFLOW = "workflow"
    KIND_ROLE = "role"
    KIND_UI = "ui"

    KIND_CHOICES = (
        (KIND_SCHEMA, "Schema pack"),
        (KIND_WORKFLOW, "Workflow pack"),
        (KIND_ROLE, "Role pack"),
        (KIND_UI, "UI pack"),
    )

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    version = models.CharField(max_length=30, default="v1")

    description = models.TextField(blank=True)

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_config_packs",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("kind", "code")

    def __str__(self) -> str:
        return f"{self.code} ({self.version})"

    def publish(self, user=None):
        self.is_published = True
        self.published_at = timezone.now()
        if user is not None:
            self.published_by = user

    def clean(self):
        if self.kind not in dict(self.KIND_CHOICES):
            raise ValidationError({"kind": "Invalid pack kind."})


class LabPackAssignment(models.Model):
    laboratory_profile = models.ForeignKey(
        LaboratoryProfile, on_delete=models.CASCADE, related_name="pack_assignments"
    )
    pack = models.ForeignKey(ConfigPack, on_delete=models.CASCADE, related_name="lab_assignments")

    is_enabled = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100, help_text="Lower number applies first")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("laboratory_profile", "pack"),)
        ordering = ("priority", "pack__code")

    def __str__(self) -> str:
        return f"{self.laboratory_profile} -> {self.pack.code} ({'on' if self.is_enabled else 'off'})"

    def clean(self):
        if self.pack and not self.pack.is_published:
            # Allow assignment, but warn at validation time
            pass


class SchemaPackItem(models.Model):
    pack = models.ForeignKey(
        ConfigPack,
        on_delete=models.CASCADE,
        related_name="schema_items",
        limit_choices_to={"kind": ConfigPack.KIND_SCHEMA},
    )
    schema = models.ForeignKey(MetadataSchema, on_delete=models.PROTECT, related_name="pack_items")
    order = models.PositiveIntegerField(default=10)
    is_required = models.BooleanField(default=False)

    class Meta:
        unique_together = (("pack", "schema"),)
        ordering = ("order", "id")

    def __str__(self) -> str:
        return f"{self.pack.code}: {self.schema.code} {self.schema.version}"

    def clean(self):
        if self.pack and self.pack.kind != ConfigPack.KIND_SCHEMA:
            raise ValidationError({"pack": "This item can only belong to a schema pack."})


class WorkflowPackDefinition(models.Model):
    OBJECT_SAMPLE = "sample"
    OBJECT_EXPERIMENT = "experiment"

    OBJECT_KIND_CHOICES = (
        (OBJECT_SAMPLE, "Sample"),
        (OBJECT_EXPERIMENT, "Experiment"),
    )

    pack = models.ForeignKey(
        ConfigPack,
        on_delete=models.CASCADE,
        related_name="workflow_defs",
        limit_choices_to={"kind": ConfigPack.KIND_WORKFLOW},
    )
    object_kind = models.CharField(max_length=30, choices=OBJECT_KIND_CHOICES)
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=30, default="v1")

    definition = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locked_workflow_defs",
    )
    lock_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("pack", "object_kind", "code", "version"),)
        ordering = ("object_kind", "code", "version")

    def __str__(self) -> str:
        return f"{self.object_kind}:{self.code} ({self.version})"

    def clean(self):
        if self.pack and self.pack.kind != ConfigPack.KIND_WORKFLOW:
            raise ValidationError({"pack": "This definition can only belong to a workflow pack."})

        # Lightweight validation for definition structure
        d = self.definition or {}
        if d == {}:
            return

        statuses = d.get("statuses", [])
        transitions = d.get("transitions", [])

        if not isinstance(statuses, list) or not isinstance(transitions, list):
            raise ValidationError({"definition": "statuses and transitions must be lists."})

        codes = [s.get("code") for s in statuses if isinstance(s, dict)]
        if any(not c for c in codes):
            raise ValidationError({"definition": "Each status must have a non-empty code."})
        if len(set(codes)) != len(codes):
            raise ValidationError({"definition": "Status codes must be unique."})

        code_set = set(codes)
        for t in transitions:
            if not isinstance(t, dict):
                raise ValidationError({"definition": "Each transition must be an object."})
            f = t.get("from")
            to = t.get("to")
            if f not in code_set or to not in code_set:
                raise ValidationError({"definition": f"Transition references unknown status: {f} -> {to}."})

    def lock(self, user=None, reason: str = ""):
        self.is_locked = True
        self.locked_at = timezone.now()
        if user is not None:
            self.locked_by = user
        if reason:
            self.lock_reason = reason


class RolePackDefinition(models.Model):
    pack = models.ForeignKey(
        ConfigPack,
        on_delete=models.CASCADE,
        related_name="role_defs",
        limit_choices_to={"kind": ConfigPack.KIND_ROLE},
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=30, default="v1")

    definition = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("pack", "code", "version"),)
        ordering = ("code", "version")

    def __str__(self) -> str:
        return f"{self.code} ({self.version})"

    def clean(self):
        if self.pack and self.pack.kind != ConfigPack.KIND_ROLE:
            raise ValidationError({"pack": "This definition can only belong to a role pack."})
