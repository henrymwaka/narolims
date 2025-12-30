# lims_core/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Institute,
    Laboratory,
    StaffMember,
    Project,
    Sample,
    Experiment,
    InventoryItem,
    UserRole,
    AuditLog,
    WorkflowTransition,
    WorkflowAlert,
)

from .labs.models import LaboratoryProfile

# Metadata schema models
from .metadata.models import (
    MetadataSchema,
    MetadataField,
)


# =============================================================
# Workflow transitions (READ-ONLY AUDIT LOG)
# =============================================================

@admin.register(WorkflowTransition)
class WorkflowTransitionAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "object_id",
        "from_status",
        "to_status",
        "performed_by",
        "laboratory",
        "created_at",
    )
    list_filter = (
        "kind",
        "from_status",
        "to_status",
        "laboratory",
    )
    search_fields = (
        "object_id",
        "performed_by__username",
    )
    ordering = ("-created_at",)

    readonly_fields = [f.name for f in WorkflowTransition._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================
# Workflow SLA alerts (READ-ONLY)
# =============================================================

@admin.register(WorkflowAlert)
class WorkflowAlertAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "object_id",
        "state",
        "severity_badge",
        "sla_seconds",
        "duration_seconds",
        "triggered_at",
        "resolved_at",
        "created_by",
    )
    list_filter = ("kind", "state")
    search_fields = ("object_id", "state")
    ordering = ("-triggered_at",)

    readonly_fields = [f.name for f in WorkflowAlert._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def severity_badge(self, obj):
        if obj.resolved_at:
            return format_html(
                '<span style="color:#2e7d32;font-weight:bold;">RESOLVED</span>'
            )

        seconds = obj.sla_seconds or 0

        if seconds >= 72 * 3600:
            return format_html(
                '<span style="color:#c62828;font-weight:bold;">CRITICAL</span>'
            )
        if seconds >= 24 * 3600:
            return format_html(
                '<span style="color:#ed6c02;font-weight:bold;">WARNING</span>'
            )
        return format_html(
            '<span style="color:#f9a825;font-weight:bold;">MINOR</span>'
        )

    severity_badge.short_description = "Severity"


# =============================================================
# Institute
# =============================================================

@admin.register(Institute)
class InstituteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


# =============================================================
# Laboratory
# =============================================================

@admin.register(Laboratory)
class LaboratoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "institute", "is_active")
    search_fields = ("code", "name")
    list_filter = ("institute", "is_active")


# =============================================================
# Laboratory Profile (CONFIGURATION LAYER)
# =============================================================

@admin.register(LaboratoryProfile)
class LaboratoryProfileAdmin(admin.ModelAdmin):
    list_display = (
        "laboratory",
        "lab_type",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "lab_type",
        "is_active",
    )

    search_fields = (
        "laboratory__code",
        "laboratory__name",
        "lab_type",
    )

    autocomplete_fields = ("laboratory",)

    fieldsets = (
        (
            "Laboratory",
            {
                "fields": (
                    "laboratory",
                    "is_active",
                ),
            },
        ),
        (
            "Classification",
            {
                "fields": (
                    "lab_type",
                    "description",
                ),
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


# =============================================================
# Metadata Schemas
# =============================================================

class MetadataFieldInline(admin.TabularInline):
    model = MetadataField
    extra = 0
    ordering = ("order",)
    fields = (
        "order",
        "code",
        "label",
        "field_type",
        "required",
        "choices",
        "help_text",
    )


@admin.register(MetadataSchema)
class MetadataSchemaAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "applies_to",
        "laboratory_profile",
        "version",
        "is_active",
        "created_at",
    )

    list_filter = (
        "applies_to",
        "laboratory_profile",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
        "laboratory_profile__laboratory__name",
        "laboratory_profile__laboratory__code",
    )

    autocomplete_fields = ("laboratory_profile",)

    inlines = (MetadataFieldInline,)

    fieldsets = (
        (
            "Schema Identity",
            {
                "fields": (
                    "laboratory_profile",
                    "code",
                    "name",
                    "description",
                ),
            },
        ),
        (
            "Scope and Versioning",
            {
                "fields": (
                    "applies_to",
                    "version",
                    "is_active",
                ),
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                ),
            },
        ),
    )

    readonly_fields = ("created_at",)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# =============================================================
# Staff
# =============================================================

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "staff_type",
        "institute",
        "laboratory",
        "is_active",
    )
    search_fields = ("full_name", "email", "phone")
    list_filter = (
        "staff_type",
        "institute",
        "laboratory",
        "is_active",
    )
    autocomplete_fields = ("user", "institute", "laboratory")


# =============================================================
# Project
# =============================================================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "laboratory", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("laboratory", "is_active")


# =============================================================
# Sample (STRICT READ-ONLY)
# =============================================================

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = (
        "sample_id",
        "sample_type",
        "status",
        "laboratory",
        "project",
        "workflow_links",
    )
    search_fields = ("sample_id",)
    list_filter = (
        "sample_type",
        "status",
        "laboratory",
        "project",
    )
    autocomplete_fields = ("laboratory", "project")

    readonly_fields = [f.name for f in Sample._meta.fields]

    def workflow_links(self, obj):
        transitions_url = (
            reverse("admin:lims_core_workflowtransition_changelist")
            + f"?kind=sample&object_id={obj.pk}"
        )
        alerts_url = (
            reverse("admin:lims_core_workflowalert_changelist")
            + f"?kind=sample&object_id={obj.pk}"
        )
        return format_html(
            '<a href="{}">Transitions</a> | <a href="{}">SLA Alerts</a>',
            transitions_url,
            alerts_url,
        )

    workflow_links.short_description = "Workflow"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================
# Experiment (STRICT READ-ONLY)
# =============================================================

@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "laboratory",
        "project",
        "created_at",
        "workflow_links",
    )
    search_fields = ("name",)
    list_filter = ("status", "laboratory", "project")
    autocomplete_fields = ("laboratory", "project")

    readonly_fields = [f.name for f in Experiment._meta.fields]

    def workflow_links(self, obj):
        transitions_url = (
            reverse("admin:lims_core_workflowtransition_changelist")
            + f"?kind=experiment&object_id={obj.pk}"
        )
        alerts_url = (
            reverse("admin:lims_core_workflowalert_changelist")
            + f"?kind=experiment&object_id={obj.pk}"
        )
        return format_html(
            '<a href="{}">Transitions</a> | <a href="{}">SLA Alerts</a>',
            transitions_url,
            alerts_url,
        )

    workflow_links.short_description = "Workflow"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================
# Inventory
# =============================================================

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity", "laboratory")
    search_fields = ("name",)
    list_filter = ("laboratory",)


# =============================================================
# User Roles
# =============================================================

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "laboratory")
    search_fields = ("user__username", "role")
    list_filter = ("laboratory", "role")


# =============================================================
# Audit Log (READ-ONLY)
# =============================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "laboratory")
    search_fields = ("action", "user__username")
    list_filter = ("laboratory", "action")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
