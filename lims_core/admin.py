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
# Workflow SLA alerts (READ-ONLY, WITH SEVERITY)
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
    list_filter = (
        "kind",
        "state",
    )
    search_fields = (
        "object_id",
        "state",
    )
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
            color = "#c62828"
            label = "CRITICAL"
        elif seconds >= 24 * 3600:
            color = "#ed6c02"
            label = "WARNING"
        else:
            color = "#f9a825"
            label = "MINOR"

        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            label,
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

    # Make all fields read-only on the object page (prevents edits via admin UI)
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

    # Block all write ops from admin
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
