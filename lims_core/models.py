from django.db import models
from django.db.models import Q, F
from django.contrib.auth.models import User


# ---------------------------------------------------------------------
# Base: adds created_at / updated_at to every model
# ---------------------------------------------------------------------
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------
class Project(TimeStampedModel):
    """A research project or study."""
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True, db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="projects_created"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Only enforce when both dates are present
            models.CheckConstraint(
                name="project_end_after_start",
                check=Q(end_date__gte=F("start_date")) | Q(start_date__isnull=True) | Q(end_date__isnull=True),
            ),
        ]


# ---------------------------------------------------------------------
# Sample
# ---------------------------------------------------------------------
class Sample(TimeStampedModel):
    """Any biological or lab sample tracked in the system."""

    class SampleType(models.TextChoices):
        DNA = "DNA", "DNA"
        RNA = "RNA", "RNA"
        TISSUE = "TISSUE", "Tissue"
        SERUM = "SERUM", "Serum"
        SOIL = "SOIL", "Soil"
        WATER = "WATER", "Water"
        OTHER = "OTHER", "Other"

    class SampleStatus(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        RECEIVED = "RECEIVED", "Received"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETE = "COMPLETE", "Complete"
        ARCHIVED = "ARCHIVED", "Archived"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="samples", db_index=True)
    sample_id = models.CharField(max_length=100, unique=True, db_index=True)
    sample_type = models.CharField(
        max_length=20, choices=SampleType.choices, default=SampleType.OTHER,
        help_text="e.g., DNA, RNA, plant tissue, serum, etc."
    )
    status = models.CharField(max_length=20, choices=SampleStatus.choices, default=SampleStatus.REGISTERED, db_index=True)
    collected_on = models.DateField(null=True, blank=True, db_index=True)
    collected_by = models.CharField(max_length=255, blank=True)
    storage_location = models.CharField(max_length=255, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.sample_id} ({self.sample_type})"

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                name="sample_id_not_blank",
                check=~Q(sample_id=""),
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="sample_proj_status_idx"),
        ]


# ---------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------
class Experiment(TimeStampedModel):
    """Experimental workflows applied to samples."""

    class ExperimentStatus(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        RUNNING = "RUNNING", "Running"
        COMPLETE = "COMPLETE", "Complete"
        ARCHIVED = "ARCHIVED", "Archived"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="experiments", db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    samples = models.ManyToManyField("Sample", related_name="experiments", blank=True)
    protocol_reference = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True, db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=ExperimentStatus.choices, default=ExperimentStatus.PLANNED, db_index=True)
    results = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} (Project: {self.project.name})"

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                name="experiment_end_after_start",
                check=Q(end_date__gte=F("start_date")) | Q(start_date__isnull=True) | Q(end_date__isnull=True),
            ),
        ]


# ---------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------
class InventoryItem(TimeStampedModel):
    """Consumables, reagents, or equipment tracked in inventory."""

    class ItemCategory(models.TextChoices):
        REAGENT = "REAGENT", "Reagent"
        CONSUMABLE = "CONSUMABLE", "Consumable"
        EQUIPMENT = "EQUIPMENT", "Equipment"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=20, choices=ItemCategory.choices, default=ItemCategory.OTHER, db_index=True)
    quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=50, default="units")
    location = models.CharField(max_length=255, blank=True, db_index=True)
    supplier = models.CharField(max_length=255, blank=True)
    lot_number = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    reorder_level = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category", "expiry_date"], name="inv_cat_exp_idx"),
        ]


# ---------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------
class UserRole(TimeStampedModel):
    """Custom roles for lab users beyond Django groups."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lims_roles", db_index=True)
    role = models.CharField(max_length=100, help_text="e.g., Technician, PI, Data Manager, Lab Manager")

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    class Meta:
        ordering = ["user__username", "role"]
        unique_together = [("user", "role")]  # prevent duplicate role assignment


# ---------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------
class AuditLog(TimeStampedModel):
    """Track actions for compliance and traceability."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, db_index=True)
    action = models.CharField(max_length=255, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        who = self.user.username if self.user else "system"
        return f"{self.created_at} - {who} - {self.action}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="audit_action_time_idx"),
        ]
