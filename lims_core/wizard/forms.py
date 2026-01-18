# lims_core/wizard/forms.py

from django import forms

from lims_core.models.core import Laboratory
from lims_core.config.models import LabPackAssignment, ConfigPack, WorkflowPackDefinition
from lims_core.labs.models import LaboratoryProfile
from lims_core.models.core import StaffMember
from lims_core.models import UserRole


def get_user_laboratories(user):
    """
    Conservative access rule for v0:
    - superuser: all labs
    - StaffMember.user: their lab
    - UserRole: labs from user roles
    If none found, returns empty queryset.
    """
    if getattr(user, "is_superuser", False):
        return Laboratory.objects.all().order_by("code", "name", "id")

    lab_ids = set()

    try:
        sm_qs = StaffMember.objects.filter(user=user, is_active=True).select_related("laboratory")
        for sm in sm_qs:
            if sm.laboratory_id:
                lab_ids.add(sm.laboratory_id)
    except Exception:
        pass

    try:
        ur_qs = UserRole.objects.filter(user=user).select_related("laboratory")
        for ur in ur_qs:
            if ur.laboratory_id:
                lab_ids.add(ur.laboratory_id)
    except Exception:
        pass

    return Laboratory.objects.filter(id__in=list(lab_ids)).order_by("code", "name", "id")


def get_workflow_templates_for_lab(lab: Laboratory):
    """
    Returns a list of (code, label, meta_dict) for workflow templates.
    We intentionally keep it loose: if no packs are configured, we return Default.
    """
    choices = []
    templates = []

    # Default fallback, always present
    templates.append(
        (
            "DEFAULT",
            "Default workflow (no pack template selected)",
            {"workflow_code": "DEFAULT", "workflow_name": "Default workflow", "workflow_version": "v1"},
        )
    )

    try:
        profile = LaboratoryProfile.objects.filter(laboratory=lab, is_active=True).first()
        if not profile:
            return templates

        pack_ids = list(
            LabPackAssignment.objects.filter(
                laboratory_profile=profile,
                is_enabled=True,
                pack__is_published=True,
                pack__kind=ConfigPack.KIND_WORKFLOW,
            )
            .order_by("priority", "id")
            .values_list("pack_id", flat=True)
        )

        if not pack_ids:
            return templates

        defs = WorkflowPackDefinition.objects.filter(
            pack_id__in=pack_ids,
            is_active=True,
            object_kind="project",
        ).order_by("pack_id", "code", "version", "id")

        for d in defs:
            code = getattr(d, "code", None) or "UNKNOWN"
            name = getattr(d, "name", None) or code
            version = getattr(d, "version", None) or "v1"
            label = f"{name} ({code}, {version})"
            templates.append(
                (
                    code,
                    label,
                    {"workflow_code": code, "workflow_name": name, "workflow_version": version},
                )
            )

    except Exception:
        return templates

    return templates


class WizardLaboratoryForm(forms.Form):
    laboratory = forms.ModelChoiceField(queryset=Laboratory.objects.none(), required=True)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["laboratory"].queryset = get_user_laboratories(user).order_by("code", "name", "id")


class WizardTemplateForm(forms.Form):
    template_code = forms.ChoiceField(required=True)

    def __init__(self, *args, lab=None, **kwargs):
        super().__init__(*args, **kwargs)
        templates = get_workflow_templates_for_lab(lab) if lab else []
        self._template_meta_by_code = {t[0]: t[2] for t in templates}
        self.fields["template_code"].choices = [(t[0], t[1]) for t in templates]


class WizardProjectDetailsForm(forms.Form):
    name = forms.CharField(max_length=255, required=True)
    description = forms.CharField(widget=forms.Textarea, required=False)


class WizardSamplePlanForm(forms.Form):
    create_placeholders = forms.BooleanField(required=False, initial=False)
    count = forms.IntegerField(required=False, min_value=0, max_value=100000, initial=0)
    sample_type = forms.CharField(required=False, max_length=64, initial="test")

    def clean(self):
        cleaned = super().clean()
        create = bool(cleaned.get("create_placeholders"))
        count = int(cleaned.get("count") or 0)
        if create and count <= 0:
            self.add_error("count", "Provide a sample count greater than 0, or uncheck placeholder creation.")
        return cleaned
