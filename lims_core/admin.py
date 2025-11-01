from django.contrib import admin
from .models import Project, Sample, Experiment, InventoryItem, UserRole, AuditLog


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "created_by", "created_at")
    search_fields = ("name", "description", "created_by__username")
    list_filter = ("start_date", "end_date")
    autocomplete_fields = ("created_by",)
    ordering = ("-created_at",)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sample_id", "project", "sample_type", "collected_on", "storage_location", "created_at")
    search_fields = ("sample_id", "project__name", "collected_by", "storage_location")
    list_filter = ("sample_type", "collected_on")
    autocomplete_fields = ("project",)
    ordering = ("-created_at",)


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "start_date", "end_date", "status", "created_at")
    search_fields = ("name", "project__name", "protocol_reference")
    list_filter = ("status", "start_date", "end_date")
    autocomplete_fields = ("project", "samples")
    filter_horizontal = ("samples",)
    ordering = ("-created_at",)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "quantity", "unit", "location", "supplier", "expiry_date", "created_at")
    search_fields = ("name", "location", "supplier", "sku", "lot_number")
    list_filter = ("category", "expiry_date")
    ordering = ("name",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "created_at")
    search_fields = ("user__username", "role")
    list_filter = ("role",)
    autocomplete_fields = ("user",)
    ordering = ("user", "role")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "ip_address")
    search_fields = ("action", "user__username", "ip_address")
    list_filter = ("action",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
