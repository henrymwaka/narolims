# lims_core/admin.py

from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

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
    list_filter = ("kind", "from_status", "to_status", "laboratory")
    search_fields = ("object_id", "performed_by__username")
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
# Laboratory Profile
# =============================================================

@admin.register(LaboratoryProfile)
class LaboratoryProfileAdmin(admin.ModelAdmin):
    list_display = ("laboratory", "lab_type", "is_active", "updated_at")
    list_filter = ("lab_type", "is_active")
    search_fields = ("laboratory__code", "laboratory__name", "lab_type")
    autocomplete_fields = ("laboratory",)

    fieldsets = (
        ("Laboratory", {"fields": ("laboratory", "is_active")}),
        ("Classification", {"fields": ("lab_type", "description")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    readonly_fields = ("created_at", "updated_at")


# =============================================================
# Metadata Schemas (ACCREDITATION-SAFE ADMIN UX)
# =============================================================

def _parse_version_str(version: str) -> int:
    if not version:
        return 1
    v = str(version).strip().lower()
    if v.startswith("v"):
        v = v[1:]
    try:
        return int(v)
    except Exception:
        return 1


def _format_version_str(n: int) -> str:
    return f"v{int(n)}"


@transaction.atomic
def _clone_schema_revision(*, schema: MetadataSchema, user, reason: str = "") -> MetadataSchema:
    current_n = _parse_version_str(schema.version or "v1")
    next_version = _format_version_str(current_n + 1)

    new_schema = MetadataSchema.objects.create(
        laboratory_profile=schema.laboratory_profile,
        analysis_context=schema.analysis_context,
        code=schema.code,
        version=next_version,
        name=schema.name,
        description=schema.description,
        applies_to=schema.applies_to,
        is_active=True,
        is_locked=False,
        supersedes=schema,
    )

    fields = schema.fields.all().order_by("order", "id")
    MetadataField.objects.bulk_create(
        [
            MetadataField(
                schema=new_schema,
                order=f.order,
                code=f.code,
                label=f.label,
                field_type=f.field_type,
                required=f.required,
                help_text=f.help_text,
                choices=f.choices,
            )
            for f in fields
        ]
    )

    return new_schema


class MetadataFieldInline(admin.TabularInline):
    model = MetadataField
    extra = 0
    ordering = ("order",)
    fields = ("order", "code", "label", "field_type", "required", "choices", "help_text")

    def _schema_locked(self, obj):
        return bool(obj and obj.is_locked)

    def get_readonly_fields(self, request, obj=None):
        if self._schema_locked(obj):
            return self.fields
        return super().get_readonly_fields(request, obj)

    def has_add_permission(self, request, obj=None):
        return not self._schema_locked(obj)

    def has_delete_permission(self, request, obj=None):
        return not self._schema_locked(obj)


@admin.register(MetadataSchema)
class MetadataSchemaAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "applies_to",
        "laboratory_profile",
        "version",
        "is_active",
        "lock_badge",
        "locked_at",
        "locked_by",
        "created_at",
    )

    list_filter = ("applies_to", "laboratory_profile", "is_active", "is_locked")
    search_fields = ("code", "name", "laboratory_profile__laboratory__name")
    autocomplete_fields = ("laboratory_profile",)
    inlines = (MetadataFieldInline,)
    actions = ("lock_selected_schemas", "create_revision_from_locked")

    fieldsets = (
        ("Schema Identity", {"fields": ("laboratory_profile", "analysis_context", "code", "name", "description")}),
        ("Scope and Versioning", {"fields": ("applies_to", "version", "is_active", "supersedes")}),
        ("Accreditation Lock", {"fields": ("is_locked", "locked_at", "locked_by", "lock_reason")}),
        ("Audit", {"fields": ("created_at",)}),
    )

    readonly_fields = ("created_at", "locked_at", "locked_by", "is_locked")

    def lock_badge(self, obj):
        return format_html(
            '<span style="font-weight:bold;color:{};">{}</span>',
            "#2e7d32" if obj.is_locked else "#ed6c02",
            "LOCKED" if obj.is_locked else "DRAFT",
        )

    lock_badge.short_description = "Lock"

    # ---------- UX SAFEGUARDS ----------

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj and obj.is_locked:
            extra_context["accreditation_warning"] = (
                "This metadata schema is locked for accreditation. "
                "Editing is disabled. Create a new revision to make changes."
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj and obj.is_locked:
            context["show_save"] = False
            context["show_save_and_continue"] = False
            context["show_save_and_add_another"] = False
        return super().render_change_form(request, context, add, change, form_url, obj)

    # ---------- HARD ENFORCEMENT ----------

    def save_model(self, request, obj, form, change):
        if change and obj.is_locked:
            raise ValidationError("This schema is locked and cannot be modified.")
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        if form.instance.is_locked:
            raise ValidationError("This schema is locked. Create a new revision.")
        super().save_formset(request, form, formset, change)

    # ---------- ACTIONS ----------

    def lock_selected_schemas(self, request, queryset):
        for s in queryset.filter(is_locked=False):
            s.is_locked = True
            s.locked_at = timezone.now()
            s.locked_by = request.user
            s.lock_reason = s.lock_reason or "Locked via admin action"
            s.save()

    lock_selected_schemas.short_description = "Lock selected schemas (accreditation)"

    def create_revision_from_locked(self, request, queryset):
        for s in queryset.filter(is_locked=True):
            _clone_schema_revision(schema=s, user=request.user)

    create_revision_from_locked.short_description = "Create new revision from locked schema"


# =============================================================
# Metadata Field (READ-ONLY WHEN LOCKED)
# =============================================================

@admin.register(MetadataField)
class MetadataFieldAdmin(admin.ModelAdmin):
    list_display = ("schema", "code", "label", "field_type", "required", "order")

    def has_change_permission(self, request, obj=None):
        return not (obj and obj.schema.is_locked)

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.schema.is_locked)


# =============================================================
# Staff
# =============================================================

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "staff_type", "institute", "laboratory", "is_active")
    autocomplete_fields = ("user", "institute", "laboratory")


# =============================================================
# Project
# =============================================================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "laboratory", "is_active", "created_at")


# =============================================================
# Sample (STRICT READ-ONLY)
# =============================================================

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    readonly_fields = [f.name for f in Sample._meta.fields]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


# =============================================================
# Experiment (STRICT READ-ONLY)
# =============================================================

@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    readonly_fields = [f.name for f in Experiment._meta.fields]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


# =============================================================
# Inventory
# =============================================================

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity", "laboratory")


# =============================================================
# User Roles
# =============================================================

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "laboratory")


# =============================================================
# Audit Log (READ-ONLY)
# =============================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
