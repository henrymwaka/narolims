# lims_core/labconfig_wizard/views_admin.py

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from lims_core.models.core import Institute, Laboratory, UserRole
from lims_core.models.drafts import LabConfigDraft
from lims_core.labs.models import LaboratoryProfile


def _labs_in_scope_for_user(user):
    if user.is_superuser:
        return Laboratory.objects.select_related("institute").all().order_by(
            "institute__code", "code", "id"
        )
    return (
        Laboratory.objects.select_related("institute")
        .filter(is_active=True, user_roles__user=user)
        .distinct()
        .order_by("institute__code", "code", "id")
    )


def _require_labconfig_admin(user):
    # Keep strict for now. Expand later if needed.
    if not user.is_authenticated:
        raise Http404("Not authenticated")
    if user.is_superuser:
        return
    raise Http404("Not permitted")


class CreateLaboratoryForm(forms.Form):
    institute = forms.ModelChoiceField(queryset=Institute.objects.none(), required=True)
    code = forms.CharField(max_length=32, required=True)
    name = forms.CharField(max_length=120, required=True)
    location = forms.CharField(max_length=120, required=False)
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        # Superuser sees all institutes. If you later permit institute admins,
        # restrict this queryset to institutes in scope.
        if user.is_superuser:
            self.fields["institute"].queryset = Institute.objects.all().order_by("code", "name", "id")
        else:
            self.fields["institute"].queryset = Institute.objects.none()

    def clean_code(self):
        return (self.cleaned_data["code"] or "").strip().upper()


@login_required
@require_http_methods(["GET"])
def manage(request):
    labs = _labs_in_scope_for_user(request.user)
    can_create = request.user.is_superuser
    return render(
        request,
        "lims_core/labconfig_wizard/manage.html",
        {
            "labs": labs,
            "can_create": can_create,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_lab(request):
    _require_labconfig_admin(request.user)

    if request.method == "POST":
        form = CreateLaboratoryForm(request.POST, user=request.user)
        if form.is_valid():
            inst = form.cleaned_data["institute"]
            code = form.cleaned_data["code"]
            name = form.cleaned_data["name"].strip()
            location = (form.cleaned_data.get("location") or "").strip()
            is_active = bool(form.cleaned_data.get("is_active", True))

            # Enforce uniqueness: (institute, code) is unique_together
            exists = Laboratory.objects.filter(institute=inst, code=code).exists()
            if exists:
                form.add_error("code", "A laboratory with this code already exists in that institute.")
            else:
                lab = Laboratory.objects.create(
                    institute=inst,
                    code=code,
                    name=name,
                    location=location or (inst.location or "Unknown"),
                    is_active=is_active,
                )

                # Ensure there is a profile (your config layer)
                LaboratoryProfile.objects.get_or_create(laboratory=lab, defaults={"is_active": True})

                messages.success(request, f"Laboratory created: {inst.code}:{lab.code}")
                return redirect(reverse("lims_core:labconfig_wizard:start_for_lab", kwargs={"lab_id": lab.id}))
    else:
        form = CreateLaboratoryForm(user=request.user)

    return render(
        request,
        "lims_core/labconfig_wizard/create_lab.html",
        {
            "form": form,
        },
    )


@login_required
@require_http_methods(["GET"])
def start_for_lab(request, lab_id: int):
    """
    Starts the configuration wizard for an existing lab by creating a draft
    and redirecting into step 2, skipping the lab selection screen.
    """
    lab = get_object_or_404(Laboratory.objects.select_related("institute"), pk=lab_id)

    # Must be in scope unless superuser
    if not request.user.is_superuser:
        in_scope = UserRole.objects.filter(user=request.user, laboratory=lab, is_active=True).exists()
        if not in_scope:
            raise Http404("Laboratory not in scope")

    # Ensure profile exists
    LaboratoryProfile.objects.get_or_create(laboratory=lab, defaults={"is_active": True})

    draft = LabConfigDraft.objects.create(
        created_by=request.user,
        laboratory=lab,
    )

    return redirect(reverse("lims_core:labconfig_wizard:step2", kwargs={"draft_id": draft.id}))
