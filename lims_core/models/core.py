# lims_core/models/core.py

default_app_config = "lims_core.apps.LimsCoreConfig"

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings

from lims_core.workflows.guards import WorkflowWriteGuardMixin


# ============================================================
# Base
# ============================================================
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ============================================================
# Institute
# ============================================================
class Institute(TimeStampedModel):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


# ============================================================
# Laboratory
# ============================================================
class Laboratory(TimeStampedModel):
    institute = models.ForeignKey(
        Institute,
        on_delete=models.PROTECT,
        related_name="laboratories",
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("institute", "code")

    def __str__(self):
        return f"{self.institute.code}:{self.code}"


# ============================================================
# Staff
# ============================================================
class StaffMember(TimeStampedModel):
    institute = models.ForeignKey(
        Institute,
        on_delete=models.PROTECT,
        related_name="staff",
    )
    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff",
    )

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_profile",
    )

    STAFF_TYPES = [
        ("EMPLOYEE", "Employee"),
        ("INTERN", "Intern"),
        ("VOLUNTEER", "Volunteer"),
        ("VISITOR", "Visitor"),
        ("CONTRACTOR", "Contractor"),
        ("STUDENT", "Student"),
    ]

    staff_type = models.CharField(max_length=20, choices=STAFF_TYPES)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        if self.laboratory and self.laboratory.institute_id != self.institute_id:
            raise ValidationError(
                "Staff laboratory must belong to the same institute."
            )

    def __str__(self):
        return self.full_name


# ============================================================
# Project
# ============================================================
class Project(TimeStampedModel):
    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        related_name="projects",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name


# ============================================================
# Sample Batch
# ============================================================
class SampleBatch(TimeStampedModel):
    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        related_name="sample_batches",
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="sample_batches",
        null=True,
        blank=True,
    )

    batch_code = models.CharField(max_length=100, unique=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.CharField(max_length=255, blank=True)
    collection_site = models.CharField(max_length=255, blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    def clean(self):
        if self.project and self.project.laboratory_id != self.laboratory_id:
            raise ValidationError(
                "Batch laboratory must match project laboratory."
            )

    def __str__(self):
        return self.batch_code


# ============================================================
# Sample
# ============================================================
class Sample(WorkflowWriteGuardMixin, TimeStampedModel):
    WORKFLOW_FIELD = "status"

    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        related_name="samples",
        null=True,
        blank=True,
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="samples",
    )

    batch = models.ForeignKey(
        SampleBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="samples",
    )

    analysis_context = models.ForeignKey(
        "lims_core.AnalysisContext",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="samples",
        help_text=(
            "Optional context used to group schemas and workflows "
            "(e.g. Soil Fertility, Food Safety)."
        ),
    )

    metadata_schema = models.ForeignKey(
        "lims_core.MetadataSchema",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bound_samples",
        help_text="Frozen metadata schema governing this sample.",
    )

    sample_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255, blank=True)
    sample_type = models.CharField(max_length=50, blank=True)

    status = models.CharField(
        max_length=50,
        default="REGISTERED",
        editable=False,
    )

    def clean(self):
        if self.laboratory and self.project.laboratory:
            if self.project.laboratory_id != self.laboratory_id:
                raise ValidationError(
                    "Sample lab must match project lab."
                )

        if self.batch and self.batch.laboratory_id != self.laboratory_id:
            raise ValidationError(
                "Sample batch must belong to same laboratory."
            )

        if self.pk:
            old = Sample.objects.only(
                "status",
                "analysis_context_id",
                "metadata_schema_id",
            ).get(pk=self.pk)

            if old.status != "REGISTERED":
                if old.analysis_context_id != self.analysis_context_id:
                    raise ValidationError(
                        "Analysis context cannot be changed after registration."
                    )
                if old.metadata_schema_id != self.metadata_schema_id:
                    raise ValidationError(
                        "Metadata schema cannot be changed after registration."
                    )

    def __str__(self):
        return self.sample_id


# ============================================================
# Experiment
# ============================================================
class Experiment(WorkflowWriteGuardMixin, TimeStampedModel):
    WORKFLOW_FIELD = "status"

    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        related_name="experiments",
        null=True,
        blank=True,
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="experiments",
    )

    analysis_context = models.ForeignKey(
        "lims_core.AnalysisContext",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experiments",
        help_text="Optional context for experiments and method development.",
    )

    metadata_schema = models.ForeignKey(
        "lims_core.MetadataSchema",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bound_experiments",
        help_text="Frozen metadata schema governing this experiment.",
    )

    name = models.CharField(max_length=255)

    status = models.CharField(
        max_length=50,
        default="PLANNED",
        editable=False,
    )

    def clean(self):
        if self.laboratory and self.project.laboratory:
            if self.project.laboratory_id != self.laboratory_id:
                raise ValidationError(
                    "Experiment lab must match project lab."
                )

        if self.pk:
            old = Experiment.objects.only(
                "status",
                "analysis_context_id",
                "metadata_schema_id",
            ).get(pk=self.pk)

            if old.status != "PLANNED":
                if old.analysis_context_id != self.analysis_context_id:
                    raise ValidationError(
                        "Analysis context cannot be changed after start."
                    )
                if old.metadata_schema_id != self.metadata_schema_id:
                    raise ValidationError(
                        "Metadata schema cannot be changed after start."
                    )

    def __str__(self):
        return self.name


# ============================================================
# Inventory
# ============================================================
class InventoryItem(TimeStampedModel):
    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        related_name="inventory",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


# ============================================================
# User Roles
# ============================================================
class UserRole(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="lims_roles",
    )
    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        related_name="user_roles",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=100)

    class Meta:
        unique_together = ("user", "laboratory", "role")

    def __str__(self):
        return f"{self.user.username} - {self.role}"


# ============================================================
# Audit Log
# ============================================================
class AuditLog(TimeStampedModel):
    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.action


# ============================================================
# Workflow Transition
# ============================================================
class WorkflowTransition(models.Model):
    kind = models.CharField(max_length=32)
    object_id = models.PositiveIntegerField()
    from_status = models.CharField(max_length=50)
    to_status = models.CharField(max_length=50)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_transitions",
    )

    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_transitions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["kind", "object_id"]),
        ]

    def __str__(self):
        return (
            f"{self.kind}:{self.object_id} "
            f"{self.from_status} -> {self.to_status}"
        )


# ============================================================
# Role Map
# ============================================================
STAFF_ROLE_MAP = {
    "EMPLOYEE": {"Technician"},
    "INTERN": set(),
    "VOLUNTEER": set(),
    "VISITOR": set(),
    "CONTRACTOR": set(),
    "STUDENT": set(),
}
