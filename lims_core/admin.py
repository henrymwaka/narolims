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
# Metadata Schemas (ACCREDITATION-SAFE ADMIN UX)
# =============================================================

def _parse_version_str(version: str) -> int:
    """
    Accepts 'v1', 'v2', '1', etc.
    Returns int, defaulting to 1.
    """
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
    """
    Creates a new editable schema revision by copying the schema + fields.
    The source schema is expected to be locked (immutability policy B).
    """
    current_n = _parse_version_str(getattr(schema, "version", "") or "v1")
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
        locked_at=None,
        locked_by=None,
        lock_reason="",
        supersedes=schema,
    )

    fields = schema.fields.all().order_by("order", "id")
    new_fields = [
        MetadataField(
            schema=new_schema,
            order=f.order,
            code=f.code,
            label=f.label,
            field_type=f.field_type,
            required=f.required,
            help_text=getattr(f, "help_text", ""),
            choices=getattr(f, "choices", ""),
        )
        for f in fields
    ]
    if new_fields:
        MetadataField.objects.bulk_create(new_fields)

    # Lightweight audit trail in lock_reason of new schema (optional, keeps zero dependencies)
    if reason:
        new_schema.description = (new_schema.description or "").strip()
        # keep description untouched; store reason in lock_reason only when locking later
        _ = user

    return new_schema


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

    def _schema_locked(self, obj) -> bool:
        return bool(obj and getattr(obj, "is_locked", False))

    def get_readonly_fields(self, request, obj=None):
        if self._schema_locked(obj):
            return self.fields
        return super().get_readonly_fields(request, obj=obj)

    def has_add_permission(self, request, obj=None):
        if self._schema_locked(obj):
            return False
        return super().has_add_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None):
        if self._schema_locked(obj):
            # allow viewing the parent page; inline editing is blocked via readonly + save guards below
            return True
        return super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if self._schema_locked(obj):
            return False
        return super().has_delete_permission(request, obj=obj)


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

    list_filter = (
        "applies_to",
        "laboratory_profile",
        "is_active",
        "is_locked",
    )

    search_fields = (
        "code",
        "name",
        "laboratory_profile__laboratory__name",
        "laboratory_profile__laboratory__code",
    )

    autocomplete_fields = ("laboratory_profile",)

    inlines = (MetadataFieldInline,)

    actions = ("lock_selected_schemas", "create_revision_from_locked")

    fieldsets = (
        (
            "Schema Identity",
            {
                "fields": (
                    "laboratory_profile",
                    "analysis_context",
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
                    "supersedes",
                ),
            },
        ),
        (
            "Accreditation Lock",
            {
                "fields": (
                    "is_locked",
                    "locked_at",
                    "locked_by",
                    "lock_reason",
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

    readonly_fields = ("created_at", "locked_at", "locked_by", "is_locked")

    def lock_badge(self, obj):
        if getattr(obj, "is_locked", False):
            return format_html('<span style="color:#2e7d32;font-weight:bold;">LOCKED</span>')
        return format_html('<span style="color:#ed6c02;font-weight:bold;">DRAFT</span>')

    lock_badge.short_description = "Lock"

    def has_delete_permission(self, request, obj=None):
        # Never allow deleting locked schemas (history must remain)
        if obj and getattr(obj, "is_locked", False):
            return False
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """
        IMPORTANT UX: allow opening/viewing locked schemas,
        but enforce immutability via save_model/save_formset.
        """
        return super().has_change_permission(request, obj=obj)

    def get_readonly_fields(self, request, obj=None):
        ro = set(super().get_readonly_fields(request, obj=obj) or [])
        if obj and getattr(obj, "is_locked", False):
            # Full read-only view once locked
            model_fields = [f.name for f in obj._meta.fields]
            ro.update(model_fields)
        return tuple(ro)

    def save_model(self, request, obj, form, change):
        if change and obj and getattr(obj, "is_locked", False):
            raise ValidationError("This schema is locked and cannot be modified. Create a new revision by cloning.")
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        parent_obj = form.instance
        if parent_obj and getattr(parent_obj, "is_locked", False):
            raise ValidationError("This schema is locked. Fields cannot be added/edited/deleted. Create a new revision by cloning.")
        super().save_formset(request, form, formset, change)

    # ----------------------------
    # Admin actions (safe workflow)
    # ----------------------------

    def lock_selected_schemas(self, request, queryset):
        locked = 0
        skipped = 0

        for s in queryset:
            if getattr(s, "is_locked", False):
                skipped += 1
                continue

            s.is_locked = True
            s.locked_at = timezone.now()
            s.locked_by = request.user
            if not getattr(s, "lock_reason", ""):
                s.lock_reason = "Locked via admin action"
            s.save(update_fields=["is_locked", "locked_at", "locked_by", "lock_reason"])
            locked += 1

        if locked:
            self.message_user(request, f"Locked {locked} schema(s).", level=messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} already locked schema(s).", level=messages.INFO)

    lock_selected_schemas.short_description = "Lock selected schemas (accreditation)"

    def create_revision_from_locked(self, request, queryset):
        created = 0
        for s in queryset:
            if not getattr(s, "is_locked", False):
                self.message_user(
                    request,
                    f"{s.code} ({s.version}) is not locked. Lock it first, then create a revision clone.",
                    level=messages.WARNING,
                )
                continue
            try:
                _clone_schema_revision(schema=s, user=request.user, reason="Admin revision clone")
                created += 1
            except Exception as exc:
                self.message_user(request, f"Failed to clone {s.code} ({s.version}): {exc}", level=messages.ERROR)

        if created:
            self.message_user(request, f"Created {created} schema revision(s).", level=messages.SUCCESS)

    create_revision_from_locked.short_description = "Create new editable revision from locked schema(s)"


@admin.register(MetadataField)
class MetadataFieldAdmin(admin.ModelAdmin):
    list_display = ("schema", "code", "label", "field_type", "required", "order", "schema_lock")
    list_filter = ("field_type", "required")
    search_fields = ("code", "label", "schema__code", "schema__name")

    def schema_lock(self, obj):
        if obj and obj.schema and getattr(obj.schema, "is_locked", False):
            return "LOCKED"
        return "DRAFT"

    schema_lock.short_description = "Schema"

    def has_change_permission(self, request, obj=None):
        if obj and obj.schema and getattr(obj.schema, "is_locked", False):
            # allow viewing but block saving
            return super().has_change_permission(request, obj=obj)
        return super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.schema and getattr(obj.schema, "is_locked", False):
            return False
        return super().has_delete_permission(request, obj=obj)

    def save_model(self, request, obj, form, change):
        if obj and obj.schema and getattr(obj.schema, "is_locked", False):
            raise ValidationError("This field belongs to a locked schema and cannot be modified. Create a schema revision clone.")
        super().save_model(request, obj, form, change)


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
