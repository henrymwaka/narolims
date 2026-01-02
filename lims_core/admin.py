# lims_core/admin.py

from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django.contrib import admin, messages
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

# Config packs
from .config.models import (
    ConfigPack,
    LabPackAssignment,
    SchemaPackItem,
    WorkflowPackDefinition,
    RolePackDefinition,
)

from .config.pack_io import pack_to_dict


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
    ordering = ("-created_at", "id")

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
    ordering = ("-triggered_at", "id")

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
    ordering = ("name", "id")


# =============================================================
# Laboratory
# =============================================================

@admin.register(Laboratory)
class LaboratoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "institute", "is_active")
    search_fields = ("code", "name")
    list_filter = ("institute", "is_active")

    # Deterministic ordering is critical for admin autocomplete pagination
    ordering = ("name", "id", "code")

    def get_queryset(self, request):
        """
        Enforce deterministic ordering everywhere (list view, autocomplete, changelist pagination).
        This avoids UnorderedObjectListWarning and prevents page drift.
        """
        qs = super().get_queryset(request)
        return qs.order_by("name", "id", "code")

    def get_search_results(self, request, queryset, search_term):
        """
        Admin autocomplete uses pagination. If the queryset is not ordered,
        Django raises UnorderedObjectListWarning and pagination can drift.
        Force deterministic order (name then id).
        """
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        return qs.order_by("name", "id", "code"), use_distinct


# =============================================================
# Packs admin
# =============================================================

class SchemaPackItemInline(admin.TabularInline):
    model = SchemaPackItem
    extra = 0
    fields = ("order", "schema", "is_required")
    autocomplete_fields = ("schema",)
    ordering = ("order", "id")


class WorkflowPackDefinitionInline(admin.StackedInline):
    model = WorkflowPackDefinition
    extra = 0
    fields = (
        "object_kind",
        "code",
        "name",
        "version",
        "is_active",
        "definition",
        "is_locked",
        "locked_at",
        "locked_by",
        "lock_reason",
    )
    readonly_fields = ("locked_at", "locked_by")

    def has_add_permission(self, request, obj=None):
        if obj and obj.kind != ConfigPack.KIND_WORKFLOW:
            return False
        return super().has_add_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj=obj)


class RolePackDefinitionInline(admin.StackedInline):
    model = RolePackDefinition
    extra = 0
    fields = ("code", "name", "version", "is_active", "definition")


@admin.register(ConfigPack)
class ConfigPackAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "kind",
        "version",
        "publish_badge",
        "published_at",
        "published_by",
        "updated_at",
    )
    list_filter = ("kind", "is_published")
    search_fields = ("code", "name", "description")
    ordering = ("kind", "code", "id")

    actions = ("publish_selected", "export_selected_json")

    fieldsets = (
        (
            "Pack Identity",
            {
                "fields": (
                    "code",
                    "name",
                    "kind",
                    "version",
                    "description",
                ),
            },
        ),
        (
            "Publishing",
            {
                "fields": (
                    "is_published",
                    "published_at",
                    "published_by",
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

    readonly_fields = ("published_at", "published_by", "created_at", "updated_at")

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []

        inlines = []
        if obj.kind == ConfigPack.KIND_SCHEMA:
            inlines.append(SchemaPackItemInline(self.model, self.admin_site))
        elif obj.kind == ConfigPack.KIND_WORKFLOW:
            inlines.append(WorkflowPackDefinitionInline(self.model, self.admin_site))
        elif obj.kind == ConfigPack.KIND_ROLE:
            inlines.append(RolePackDefinitionInline(self.model, self.admin_site))
        return inlines

    def publish_badge(self, obj):
        if obj.is_published:
            return format_html(
                '<span style="color:#2e7d32;font-weight:bold;">PUBLISHED</span>'
            )
        return format_html('<span style="color:#ed6c02;font-weight:bold;">DRAFT</span>')

    publish_badge.short_description = "State"

    def publish_selected(self, request, queryset):
        n = 0
        for p in queryset:
            if p.is_published:
                continue
            p.publish(user=request.user)
            p.save(update_fields=["is_published", "published_at", "published_by", "updated_at"])
            n += 1
        self.message_user(request, f"Published {n} pack(s).", level=messages.SUCCESS)

    publish_selected.short_description = "Publish selected packs"

    def export_selected_json(self, request, queryset):
        payload = [pack_to_dict(p) for p in queryset.order_by("kind", "code", "id")]
        return JsonResponse(payload, safe=False)

    export_selected_json.short_description = "Export selected packs as JSON"


class LabPackAssignmentInline(admin.TabularInline):
    model = LabPackAssignment
    extra = 0
    fields = ("pack", "is_enabled", "priority")
    autocomplete_fields = ("pack",)
    ordering = ("priority", "id")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("pack")


@admin.register(LabPackAssignment)
class LabPackAssignmentAdmin(admin.ModelAdmin):
    list_display = ("laboratory_profile", "pack", "is_enabled", "priority", "updated_at")
    list_filter = ("is_enabled", "pack__kind", "pack__is_published")
    search_fields = ("laboratory_profile__laboratory__name", "pack__code", "pack__name")
    autocomplete_fields = ("laboratory_profile", "pack")
    ordering = ("laboratory_profile__laboratory__name", "priority", "id")


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

    inlines = (LabPackAssignmentInline,)

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
    ordering = ("laboratory__name", "id")


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
    The source schema is expected to be locked.
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

    if reason:
        _ = user

    return new_schema


class MetadataFieldInline(admin.TabularInline):
    model = MetadataField
    extra = 0
    ordering = ("order", "id")
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

    ordering = ("code", "version", "-created_at", "id")

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

    change_form_template = "admin/lims_core/metadata_schema_change_form.html"
    change_list_template = "admin/lims_core/metadataschema/change_list.html"

    def lock_badge(self, obj):
        if getattr(obj, "is_locked", False):
            return format_html(
                '<span class="lock-badge" data-locked="1" style="color:#2e7d32;font-weight:bold;">LOCKED</span>'
            )
        return format_html(
            '<span class="lock-badge" data-locked="0" style="color:#ed6c02;font-weight:bold;">DRAFT</span>'
        )

    lock_badge.short_description = "Lock"

    def has_delete_permission(self, request, obj=None):
        if obj and getattr(obj, "is_locked", False):
            return False
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        ro = set(super().get_readonly_fields(request, obj=obj) or [])
        if obj and getattr(obj, "is_locked", False):
            model_fields = [f.name for f in obj._meta.fields]
            ro.update(model_fields)
        return tuple(ro)

    def save_model(self, request, obj, form, change):
        if change and obj and getattr(obj, "is_locked", False):
            raise ValidationError(
                "This schema is locked and cannot be modified. Create a new revision by cloning."
            )
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        parent_obj = form.instance
        if parent_obj and getattr(parent_obj, "is_locked", False):
            raise ValidationError(
                "This schema is locked. Fields cannot be added, edited, or deleted."
            )
        super().save_formset(request, form, formset, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/create-revision/",
                self.admin_site.admin_view(self.create_revision_view),
                name="metadata_schema_create_revision",
            ),
        ]
        return custom_urls + urls

    def create_revision_view(self, request, object_id):
        schema = self.get_object(request, object_id)

        if not schema:
            self.message_user(request, "Schema not found.", level=messages.ERROR)
            return HttpResponseRedirect("../../")

        if not schema.is_locked:
            self.message_user(
                request,
                "Schema must be locked before creating a new revision.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect("../")

        new_schema = _clone_schema_revision(
            schema=schema,
            user=request.user,
            reason="Admin button revision clone",
        )

        self.message_user(
            request,
            f"New editable revision created: {new_schema.code} ({new_schema.version})",
            level=messages.SUCCESS,
        )

        return HttpResponseRedirect(
            reverse("admin:lims_core_metadataschema_change", args=[new_schema.pk])
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        selected = request.POST.getlist("_selected_action") or request.GET.getlist("_selected_action")
        if not selected:
            return actions

        qs = MetadataSchema.objects.filter(pk__in=selected)

        if "lock_selected_schemas" in actions:
            if not qs.filter(is_locked=False).exists():
                actions.pop("lock_selected_schemas", None)

        if "create_revision_from_locked" in actions:
            if qs.exists() and qs.filter(is_locked=False).exists():
                actions.pop("create_revision_from_locked", None)

        return actions

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = None
        if object_id:
            obj = self.get_object(request, object_id)
        extra_context["schema_is_locked"] = bool(obj and getattr(obj, "is_locked", False))
        return super().changeform_view(request, object_id, form_url, extra_context)

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
                self.message_user(
                    request,
                    f"Failed to clone {s.code} ({s.version}): {exc}",
                    level=messages.ERROR,
                )

        if created:
            self.message_user(request, f"Created {created} schema revision(s).", level=messages.SUCCESS)

    create_revision_from_locked.short_description = "Create new editable revision from locked schema(s)"


@admin.register(MetadataField)
class MetadataFieldAdmin(admin.ModelAdmin):
    list_display = ("schema", "code", "label", "field_type", "required", "order", "schema_lock")
    list_filter = ("field_type", "required")
    search_fields = ("code", "label", "schema__code", "schema__name")
    ordering = ("schema__code", "order", "id")

    def schema_lock(self, obj):
        if obj and obj.schema and getattr(obj.schema, "is_locked", False):
            return "LOCKED"
        return "DRAFT"

    schema_lock.short_description = "Schema"

    def has_delete_permission(self, request, obj=None):
        if obj and obj.schema and getattr(obj.schema, "is_locked", False):
            return False
        return super().has_delete_permission(request, obj=obj)

    def save_model(self, request, obj, form, change):
        if obj and obj.schema and getattr(obj.schema, "is_locked", False):
            raise ValidationError(
                "This field belongs to a locked schema and cannot be modified. Create a schema revision clone."
            )
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
    ordering = ("full_name", "id")


# =============================================================
# Project
# =============================================================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "laboratory", "is_active", "created_at")
    search_fields = ("name", "code")
    list_filter = ("laboratory", "is_active")

    # Deterministic ordering is critical for admin autocomplete pagination
    ordering = ("-created_at", "code", "id")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by("-created_at", "code", "id")

    def get_search_results(self, request, queryset, search_term):
        """
        Fix UnorderedObjectListWarning for admin autocomplete pagination.
        Force deterministic ordering for search results.
        """
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        return qs.order_by("-created_at", "code", "id"), use_distinct


# =============================================================
# Sample (ALLOW ADD, ENFORCE AUDIT-SAFE RULES, AUTO ASSIGN sample_id)
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
    search_fields = ("sample_id", "name")
    list_filter = (
        "sample_type",
        "status",
        "laboratory",
        "project",
    )
    autocomplete_fields = ("laboratory", "project")
    ordering = ("-created_at", "sample_id", "id")

    def get_readonly_fields(self, request, obj=None):
        """
        Allow creating samples in admin, but keep system-managed fields read-only.
        """
        base = [
            "id",
            "created_at",
            "updated_at",
            "sample_id",
            "metadata_schema",
            "analysis_context",
        ]
        if obj is not None:
            base.append("status")
        return base

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
        return request.user.is_superuser or request.user.has_perm("lims_core.add_sample")

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm("lims_core.change_sample")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        """
        Ensure sample_id is assigned for admin-created samples.
        Uses PK-based ID for uniqueness and stability.
        """
        super().save_model(request, obj, form, change)

        if obj and not (obj.sample_id or "").strip():
            lab_code = getattr(getattr(obj, "laboratory", None), "code", None) or "LAB"
            stamp = timezone.now().strftime("%Y%m%d")
            generated = f"S-{lab_code}-{stamp}-{obj.pk:06d}"

            Sample.objects.filter(pk=obj.pk).update(sample_id=generated)
            obj.sample_id = generated


# =============================================================
# Experiment (ALLOW ADD, CONTROL EDITING VIA READONLY FIELDS, NO DELETE)
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
    ordering = ("-created_at", "name", "id")

    def get_readonly_fields(self, request, obj=None):
        """
        Allow creating experiments in admin, but keep workflow-managed status read-only after creation.
        """
        base = [
            "id",
            "created_at",
            "updated_at",
        ]
        if obj is not None:
            base.append("status")
        return base

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
        return request.user.is_superuser or request.user.has_perm("lims_core.add_experiment")

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm("lims_core.change_experiment")

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
    ordering = ("name", "id")


# =============================================================
# User Roles
# =============================================================

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "laboratory")
    search_fields = ("user__username", "role")
    list_filter = ("laboratory", "role")
    ordering = ("laboratory__name", "user__username", "id")


# =============================================================
# Audit Log (READ-ONLY)
# =============================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "laboratory")
    search_fields = ("action", "user__username")
    list_filter = ("laboratory", "action")
    ordering = ("-created_at", "id")

    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
