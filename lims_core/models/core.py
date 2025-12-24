default_app_config = "lims_core.apps.LimsCoreConfig"

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings


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
# Sample
# ============================================================
class Sample(TimeStampedModel):
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

    sample_id = models.CharField(max_length=100, unique=True)
    sample_type = models.CharField(max_length=50)
    status = models.CharField(max_length=50, default="REGISTERED")

    def clean(self):
        if self.laboratory and self.project.laboratory:
            if self.project.laboratory_id != self.laboratory_id:
                raise ValidationError("Sample lab must match project lab.")

    def __str__(self):
        return self.sample_id


# ============================================================
# Experiment
# ============================================================
class Experiment(TimeStampedModel):
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

    name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default="PLANNED")

    def clean(self):
        if self.laboratory and self.project.laboratory:
            if self.project.laboratory_id != self.laboratory_id:
                raise ValidationError("Experiment lab must match project lab.")

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
# User Roles (lab-scoped, migration-safe)
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
# Workflow Transition (STATUS TIMELINE)
# ============================================================
class WorkflowTransition(models.Model):
    kind = models.CharField(max_length=32)  # sample | experiment
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
# Role Map (signals-safe)
# ============================================================
STAFF_ROLE_MAP = {
    "EMPLOYEE": {"Technician"},
    "INTERN": set(),
    "VOLUNTEER": set(),
    "VISITOR": set(),
    "CONTRACTOR": set(),
    "STUDENT": set(),
}
