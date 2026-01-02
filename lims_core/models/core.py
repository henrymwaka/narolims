# lims_core/models/core.py

default_app_config = "lims_core.apps.LimsCoreConfig"

import re
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

from lims_core.workflows.guards import WorkflowWriteGuardMixin


# ============================================================
# Metadata schema freezing (C3)
# ============================================================

def _get_laboratory_for_obj(obj):
    """
    Best-effort lab resolution.
    Prefer obj.laboratory, otherwise use project.laboratory.
    """
    lab = getattr(obj, "laboratory", None)
    if lab:
        return lab
    project = getattr(obj, "project", None)
    if project and getattr(project, "laboratory", None):
        return project.laboratory
    return None


def _get_profile_for_laboratory(lab):
    if not lab:
        return None
    return getattr(lab, "profile", None)


def _get_effective_analysis_context(obj, profile):
    ctx = getattr(obj, "analysis_context", None)
    if ctx is not None:
        return ctx
    if profile is not None:
        return getattr(profile, "default_analysis_context", None)
    return None


def _freeze_metadata_schema_if_missing(*, obj, applies_to: str):
    """
    Freeze metadata_schema once, on first save, if missing.
    Uses resolve_metadata_schema():
      - accreditation_mode True -> locked-only
      - accreditation_mode False -> latest active (locked or unlocked)
    """
    if getattr(obj, "metadata_schema_id", None):
        return

    lab = _get_laboratory_for_obj(obj)
    profile = _get_profile_for_laboratory(lab)

    if profile is None:
        return

    analysis_context = _get_effective_analysis_context(obj, profile)

    from lims_core.metadata.schema_resolver import resolve_metadata_schema

    try:
        schema = resolve_metadata_schema(
            laboratory_profile=profile,
            applies_to=applies_to,
            analysis_context=analysis_context,
        )
    except Exception as exc:
        raise ValidationError(
            f"Unable to resolve metadata schema for {applies_to}. "
            f"Check LaboratoryProfile schema configuration and accreditation mode. "
            f"Reason: {exc}"
        )

    obj.metadata_schema = schema


# ============================================================
# Helpers for codes and IDs
# ============================================================

_code_re = re.compile(r"[^A-Za-z0-9]+")


def _tokenize(value: str, *, max_len: int = 16, fallback: str = "X") -> str:
    if value is None:
        return fallback
    v = _code_re.sub("", str(value).strip().upper())
    if not v:
        return fallback
    return v[:max_len]


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


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
            raise ValidationError("Staff laboratory must belong to the same institute.")

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

    # Model allows NULL to avoid interactive migration prompts.
    # Save() guarantees a real string so DB NOT NULL is satisfied.
    code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Short project code used in sample IDs (e.g. BGEN25).",
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

    def clean(self):
        if self.laboratory_id is None:
            raise ValidationError("Project must be assigned to a laboratory.")

    def _generate_code(self) -> str:
        base = _tokenize(self.name, max_len=18, fallback="PROJECT")
        ymd = timezone.localdate().strftime("%y%m%d")
        return f"{base}{ymd}"

    def save(self, *args, **kwargs):
        if _is_blank(self.code):
            self.code = self._generate_code()
        return super().save(*args, **kwargs)

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
            raise ValidationError("Batch laboratory must match project laboratory.")

    def __str__(self):
        return self.batch_code


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

    code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Short experiment code used in sample IDs (e.g. TC01, PCR01).",
    )

    # Make these nullable to stop the makemigrations interactive prompt
    objective = models.TextField(
        null=True,
        blank=True,
        help_text="Objective statement for this experiment within the project.",
    )

    narrative = models.TextField(
        null=True,
        blank=True,
        help_text="Short narrative describing context, methods, or rationale.",
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

    def save(self, *args, **kwargs):
        if self.laboratory_id is None and self.project_id and self.project.laboratory_id:
            self.laboratory_id = self.project.laboratory_id

        if self.pk is None:
            _freeze_metadata_schema_if_missing(obj=self, applies_to="experiment")

        return super().save(*args, **kwargs)

    def clean(self):
        if self.project_id and self.project.laboratory_id and self.laboratory_id:
            if self.project.laboratory_id != self.laboratory_id:
                raise ValidationError("Experiment lab must match project lab.")

        if self.pk:
            old = Experiment.objects.only(
                "status",
                "analysis_context_id",
                "metadata_schema_id",
            ).get(pk=self.pk)

            if old.status != "PLANNED":
                if old.analysis_context_id != self.analysis_context_id:
                    raise ValidationError("Analysis context cannot be changed after start.")
                if old.metadata_schema_id != self.metadata_schema_id:
                    raise ValidationError("Metadata schema cannot be changed after start.")

    def __str__(self):
        return self.name


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

    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="samples",
        help_text="Optional experiment grouping inside the project.",
    )

    batch = models.ForeignKey(
        SampleBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="samples",
    )

    subgroup = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional label like timepoint, replicate, plate, or cohort (e.g. T0, Rep2, Plate03).",
    )

    external_id = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
        help_text="Optional client or legacy ID if samples came with pre-existing labels.",
    )

    analysis_context = models.ForeignKey(
        "lims_core.AnalysisContext",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="samples",
        help_text="Optional context used to group schemas and workflows.",
    )

    metadata_schema = models.ForeignKey(
        "lims_core.MetadataSchema",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bound_samples",
        help_text="Frozen metadata schema governing this sample.",
    )

    sample_id = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=255, blank=True)
    sample_type = models.CharField(max_length=50, blank=True)

    status = models.CharField(
        max_length=50,
        default="REGISTERED",
        editable=False,
    )

    def _build_sample_id_prefix(self) -> str:
        lab_code = _tokenize(getattr(self.laboratory, "code", None), max_len=12, fallback="LAB")
        proj_code = _tokenize(getattr(self.project, "code", None), max_len=12, fallback="PROJ")
        exp_code = "GEN"
        if self.experiment_id:
            exp_code = _tokenize(getattr(self.experiment, "code", None), max_len=12, fallback="EXP")

        ymd = timezone.localdate().strftime("%Y%m%d")
        return f"{lab_code}-{proj_code}-{exp_code}-{ymd}"

    def _next_sequence_for_prefix(self, prefix: str) -> int:
        qs = Sample.objects.filter(sample_id__startswith=prefix + "-").values_list("sample_id", flat=True)
        max_seq = 0
        for sid in qs:
            parts = str(sid).split("-")
            if len(parts) < 5:
                continue
            tail = parts[-1]
            if tail.isdigit():
                max_seq = max(max_seq, int(tail))
        return max_seq + 1

    def _generate_sample_id(self) -> str:
        prefix = self._build_sample_id_prefix()
        for _ in range(20):
            with transaction.atomic():
                seq = self._next_sequence_for_prefix(prefix)
                candidate = f"{prefix}-{seq:04d}"
                if not Sample.objects.filter(sample_id=candidate).exists():
                    return candidate

        stamp = timezone.now().strftime("%H%M%S%f")
        return f"{prefix}-{stamp}"

    def save(self, *args, **kwargs):
        if self.laboratory_id is None and self.project_id and self.project.laboratory_id:
            self.laboratory_id = self.project.laboratory_id

        if _is_blank(self.sample_id):
            self.sample_id = self._generate_sample_id()

        if self.pk is None:
            _freeze_metadata_schema_if_missing(obj=self, applies_to="sample")

        return super().save(*args, **kwargs)

    def clean(self):
        if self.project_id and self.project.laboratory_id and self.laboratory_id:
            if self.project.laboratory_id != self.laboratory_id:
                raise ValidationError("Sample lab must match project lab.")

        if self.experiment_id:
            if self.experiment.project_id != self.project_id:
                raise ValidationError("Sample experiment must belong to the same project.")
            if self.experiment.laboratory_id and self.laboratory_id:
                if self.experiment.laboratory_id != self.laboratory_id:
                    raise ValidationError("Sample experiment lab must match sample lab.")

        if self.batch_id and self.laboratory_id:
            if self.batch.laboratory_id != self.laboratory_id:
                raise ValidationError("Sample batch must belong to same laboratory.")

        if self.pk:
            old = Sample.objects.only(
                "status",
                "analysis_context_id",
                "metadata_schema_id",
            ).get(pk=self.pk)

            if old.status != "REGISTERED":
                if old.analysis_context_id != self.analysis_context_id:
                    raise ValidationError("Analysis context cannot be changed after registration.")
                if old.metadata_schema_id != self.metadata_schema_id:
                    raise ValidationError("Metadata schema cannot be changed after registration.")

    def __str__(self):
        return self.sample_id


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
        return f"{self.kind}:{self.object_id} {self.from_status} -> {self.to_status}"


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
