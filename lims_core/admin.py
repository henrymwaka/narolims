from django.contrib import admin

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
# Sample (workflow protected)
# =============================================================

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = (
        "sample_id",
        "sample_type",
        "status",
        "laboratory",
        "project",
    )
    search_fields = ("sample_id",)
    list_filter = (
        "sample_type",
        "status",
        "laboratory",
        "project",
    )
    autocomplete_fields = ("laboratory", "project")

    readonly_fields = ("status",)


# =============================================================
# Experiment (workflow protected)
# =============================================================

@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "laboratory",
        "project",
        "created_at",
    )
    search_fields = ("name",)
    list_filter = ("status", "laboratory", "project")
    autocomplete_fields = ("laboratory", "project")

    readonly_fields = ("status",)


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
# Audit Log
# =============================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "laboratory")
    search_fields = ("action", "user__username")
    list_filter = ("laboratory", "action")
    readonly_fields = ("created_at",)
