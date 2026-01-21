# lims_core/labconfig_wizard/views.py

from __future__ import annotations

import logging
from typing import Any

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from lims_core.models.core import Laboratory, UserRole
from lims_core.models.drafts import LabConfigDraft
from lims_core.labs.models import LaboratoryProfile
from lims_core.config.models import ConfigPack, LabPackAssignment
from lims_core.labconfig_wizard.services import apply_labconfig_draft

logger = logging.getLogger(__name__)

SHARED_PACK_PREFIXES = ("core_", "shared_")

LAB_PREFIX_MAP = {
    "PTC": "ptc",
    "FBA": "fba",
    "FBCL": "fbcl",
    "NALIRRI-FSL": "fsl",
    "NARL-BIOTECH": "biotech",
    "CENTRAL": "central",
    "NARL-SOILS": "soils",
}


def _require_staff(request):
    if not (request.user.is_staff or request.user.is_superuser):
        raise Http404("Not permitted")


def _model_field_names(model) -> set[str]:
    try:
        return {f.name for f in model._meta.get_fields()}
    except Exception:
        return set()


def _has_field(model, name: str) -> bool:
    return name in _model_field_names(model)


def _user_lab_ids(user) -> list[int]:
    if getattr(user, "is_superuser", False):
        return list(Laboratory.objects.values_list("id", flat=True))
    return list(
        UserRole.objects.filter(user=user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )


def _draft_for_user_or_404(*, request, draft_id: int) -> LabConfigDraft:
    qs = LabConfigDraft.objects.all()
    if not request.user.is_superuser:
        qs = qs.filter(created_by=request.user)
    return get_object_or_404(qs, pk=draft_id)


def _analysis_context_choices():
    try:
        AnalysisContext = apps.get_model("lims_core", "AnalysisContext")
    except Exception:
        return [("", "None")]

    qs = AnalysisContext.objects.all().order_by("code", "id")
    out = [("", "None")]
    for a in qs:
        code = getattr(a, "code", "") or ""
        name = getattr(a, "name", "") or ""
        label = (f"{code} - {name}").strip().strip("-").strip()
        out.append((str(a.id), label or str(a.id)))
    return out


def _get_or_init_payload_profile(profile: LaboratoryProfile | None):
    if not profile:
        return {
            "lab_type": "",
            "description": "",
            "accreditation_mode": False,
            "schema_code": "INTAKE_CORE",
            "schema_version": "v1",
            "default_analysis_context_id": "",
        }

    return {
        "lab_type": getattr(profile, "lab_type", "") or "",
        "description": getattr(profile, "description", "") or "",
        "accreditation_mode": bool(getattr(profile, "accreditation_mode", False)),
        "schema_code": getattr(profile, "schema_code", "") or "INTAKE_CORE",
        "schema_version": getattr(profile, "schema_version", "") or "v1",
        "default_analysis_context_id": str(
            getattr(profile, "default_analysis_context_id", "") or ""
        ),
    }


def _lab_prefix(lab: Laboratory) -> str:
    code = (getattr(lab, "code", "") or "").strip()
    if code in LAB_PREFIX_MAP:
        return LAB_PREFIX_MAP[code]
    return (code or "lab").lower().replace("-", "_")


def _existing_assignments(profile: LaboratoryProfile | None) -> dict[int, dict[str, Any]]:
    if not profile:
        return {}

    try:
        fk_candidates = ("laboratory_profile", "lab_profile", "profile")
        fk_field = None
        fields = _model_field_names(LabPackAssignment)
        for cand in fk_candidates:
            if cand in fields:
                fk_field = cand
                break

        if not fk_field:
            logger.warning(
                "LabPackAssignment has no expected FK to LaboratoryProfile. Fields=%s",
                sorted(fields),
            )
            return {}

        qs = LabPackAssignment.objects.filter(**{fk_field: profile}).select_related(
            "pack"
        )

        if _has_field(LabPackAssignment, "priority"):
            qs = qs.order_by("priority", "id")
        else:
            qs = qs.order_by("id")

        out: dict[int, dict[str, Any]] = {}
        for r in qs:
            pack_id = getattr(r, "pack_id", None)
            if pack_id is None:
                continue
            out[int(pack_id)] = {
                "is_enabled": bool(getattr(r, "is_enabled", False)),
                "priority": int(getattr(r, "priority", 0) or 0),
            }
        return out
    except Exception:
        logger.exception(
            "Failed to load existing LabPackAssignment rows for profile_id=%s",
            getattr(profile, "id", None),
        )
        return {}


def _published_packs_qs():
    qs = ConfigPack.objects.all()

    try:
        fields = _model_field_names(ConfigPack)

        if "is_published" in fields:
            qs = qs.filter(is_published=True)
        elif "published" in fields:
            qs = qs.filter(published=True)
        elif "status" in fields:
            qs = qs.filter(status__iexact="published")

        order_fields = []
        for f in ("kind", "code", "id"):
            if f in fields:
                order_fields.append(f)
        if not order_fields:
            order_fields = ["id"]
        return qs.order_by(*order_fields)
    except Exception:
        logger.exception(
            "Failed building published ConfigPack queryset, falling back to all packs ordered by id"
        )
        return qs.order_by("id")


def _packs_for_lab(lab: Laboratory, *, show_all: bool = False):
    packs = _published_packs_qs()
    if show_all:
        return packs

    prefix = _lab_prefix(lab)
    q = Q(code__startswith=f"{prefix}_")
    for pfx in SHARED_PACK_PREFIXES:
        q |= Q(code__startswith=pfx)
    return packs.filter(q)


def _assignment_fk_field() -> str | None:
    """
    LabPackAssignment FK name varies across iterations of the codebase.
    This resolves it once and reuses it.
    """
    fields = _model_field_names(LabPackAssignment)
    for cand in ("laboratory_profile", "lab_profile", "profile"):
        if cand in fields:
            return cand
    return None


@login_required
def overview(request):
    """
    Dedicated hub page for lab configuration.
    This should be the natural landing page for /lims/labconfig/.
    """
    _require_staff(request)

    lab_ids = _user_lab_ids(request.user)

    labs = (
        Laboratory.objects.select_related("institute")
        .filter(id__in=lab_ids)
        .order_by("institute__name", "name", "code", "id")
    )

    profiles = {
        p.laboratory_id: p
        for p in LaboratoryProfile.objects.filter(laboratory_id__in=lab_ids)
    }

    packs_by_lab: dict[int, list[LabPackAssignment]] = {}
    fk_field = _assignment_fk_field()
    if fk_field:
        qs = (
            LabPackAssignment.objects.select_related(
                "pack",
                fk_field,
            )
            .filter(**{f"{fk_field}__laboratory_id__in": lab_ids})
        )

        if _has_field(LabPackAssignment, "priority"):
            qs = qs.order_by(f"{fk_field}__laboratory_id", "priority", "id")
        else:
            qs = qs.order_by(f"{fk_field}__laboratory_id", "id")

        for a in qs:
            prof = getattr(a, fk_field, None)
            if not prof:
                continue
            packs_by_lab.setdefault(int(prof.laboratory_id), []).append(a)

    # Drafts summary (only show own drafts unless superuser)
    drafts_qs = LabConfigDraft.objects.select_related("laboratory", "created_by")
    if not request.user.is_superuser:
        drafts_qs = drafts_qs.filter(created_by=request.user)

    draft_fields = _model_field_names(LabConfigDraft)
    if "updated_at" in draft_fields:
        drafts_qs = drafts_qs.order_by("-updated_at", "-id")
    elif "created_at" in draft_fields:
        drafts_qs = drafts_qs.order_by("-created_at", "-id")
    else:
        drafts_qs = drafts_qs.order_by("-id")

    drafts = list(drafts_qs[:50])

    return render(
        request,
        "lims_core/labconfig_wizard/overview.html",
        {
            "labs": labs,
            "profiles": profiles,
            "packs_by_lab": packs_by_lab,
            "drafts": drafts,
        },
    )


@login_required
def manage(request):
    """
    Wizard router.

    Deterministic behavior:
    - Default: go to Step 1 (select lab)
    - Resume only when explicit:
      - ?draft=<id>  OR
      - ?resume=1 (resume latest draft for this user)
    - Force new:
      - ?new=1
    """
    _require_staff(request)

    try:
        if (request.GET.get("new") or "").strip() in ("1", "true", "yes", "on"):
            return redirect(reverse("lims_core:labconfig_wizard:step1"))

        draft_id_raw = (request.GET.get("draft") or "").strip()
        if draft_id_raw:
            try:
                did = int(draft_id_raw)
            except Exception:
                did = None

            if did:
                draft = _draft_for_user_or_404(request=request, draft_id=did)
                step = int(getattr(draft, "current_step", 0) or 0)
                if step <= 0:
                    return redirect(reverse("lims_core:labconfig_wizard:step1"))
                if step == 1:
                    return redirect(
                        reverse(
                            "lims_core:labconfig_wizard:step2",
                            kwargs={"draft_id": draft.id},
                        )
                    )
                if step == 2:
                    return redirect(
                        reverse(
                            "lims_core:labconfig_wizard:step3",
                            kwargs={"draft_id": draft.id},
                        )
                    )
                return redirect(
                    reverse(
                        "lims_core:labconfig_wizard:step4",
                        kwargs={"draft_id": draft.id},
                    )
                )

        resume = (request.GET.get("resume") or "").strip() in ("1", "true", "yes", "on")
        if not resume:
            return redirect(reverse("lims_core:labconfig_wizard:step1"))

        qs = LabConfigDraft.objects.all()

        all_drafts = (request.GET.get("all_drafts") or "").strip() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if not (request.user.is_superuser and all_drafts):
            qs = qs.filter(created_by=request.user)

        draft_fields = _model_field_names(LabConfigDraft)
        if "updated_at" in draft_fields:
            qs = qs.order_by("-updated_at", "-id")
        elif "created_at" in draft_fields:
            qs = qs.order_by("-created_at", "-id")
        else:
            qs = qs.order_by("-id")

        draft = qs.first()
        if not draft:
            return redirect(reverse("lims_core:labconfig_wizard:step1"))

        step = int(getattr(draft, "current_step", 0) or 0)
        if step <= 0:
            return redirect(reverse("lims_core:labconfig_wizard:step1"))
        if step == 1:
            return redirect(
                reverse(
                    "lims_core:labconfig_wizard:step2", kwargs={"draft_id": draft.id}
                )
            )
        if step == 2:
            return redirect(
                reverse(
                    "lims_core:labconfig_wizard:step3", kwargs={"draft_id": draft.id}
                )
            )
        return redirect(
            reverse("lims_core:labconfig_wizard:step4", kwargs={"draft_id": draft.id})
        )

    except Exception:
        logger.exception(
            "labconfig manage() failed for user_id=%s", getattr(request.user, "id", None)
        )
        raise


@login_required
def create_lab(request):
    _require_staff(request)
    messages.info(
        request,
        "Create-lab is not enabled in this build. Use Step 1 to select an existing lab.",
    )
    return redirect(reverse("lims_core:labconfig_wizard:step1"))


@login_required
def step1(request):
    _require_staff(request)

    lab_ids = _user_lab_ids(request.user)

    labs_qs = (
        Laboratory.objects.select_related("institute")
        .filter(id__in=lab_ids)
        .order_by("institute__name", "name", "code", "id")
    )

    if not labs_qs.exists():
        return render(
            request,
            "lims_core/labconfig_wizard/step1.html",
            {"labs": [], "error": "No laboratory scope is assigned to your account."},
        )

    if request.method == "POST":
        lab_id_raw = (request.POST.get("laboratory_id") or "").strip()
        try:
            lab_id = int(lab_id_raw)
        except Exception:
            lab_id = None

        if not lab_id or lab_id not in lab_ids:
            return render(
                request,
                "lims_core/labconfig_wizard/step1.html",
                {"labs": labs_qs, "error": "Select a laboratory in your scope."},
            )

        lab = get_object_or_404(Laboratory, pk=lab_id)

        # Delete old drafts for this user and lab to prevent "resume junk".
        LabConfigDraft.objects.filter(created_by=request.user, laboratory=lab).delete()

        draft = LabConfigDraft.objects.create(
            created_by=request.user,
            laboratory=lab,
            payload={"laboratory_id": lab.id},
            current_step=1,
        )
        return redirect(
            reverse("lims_core:labconfig_wizard:step2", kwargs={"draft_id": draft.id})
        )

    return render(request, "lims_core/labconfig_wizard/step1.html", {"labs": labs_qs})


@login_required
def step2(request, draft_id: int):
    _require_staff(request)

    draft = _draft_for_user_or_404(request=request, draft_id=draft_id)
    payload = draft.payload or {}
    lab_id = payload.get("laboratory_id") or draft.laboratory_id
    if not lab_id:
        return redirect(reverse("lims_core:labconfig_wizard:step1"))

    lab = get_object_or_404(Laboratory, pk=int(lab_id))
    profile = LaboratoryProfile.objects.filter(laboratory=lab).first()

    base_form_data = payload.get("profile") or _get_or_init_payload_profile(profile)
    form_data = dict(base_form_data)

    if request.method == "POST":
        lab_type = (request.POST.get("lab_type") or "").strip()
        description = (request.POST.get("description") or "").strip()
        accreditation_mode = (request.POST.get("accreditation_mode") or "") in (
            "1",
            "true",
            "on",
            "yes",
        )
        schema_code = (request.POST.get("schema_code") or "").strip()
        schema_version = (request.POST.get("schema_version") or "v1").strip() or "v1"
        default_ctx_id = (request.POST.get("default_analysis_context_id") or "").strip()

        form_data = {
            "lab_type": lab_type,
            "description": description,
            "accreditation_mode": bool(accreditation_mode),
            "schema_code": schema_code,
            "schema_version": schema_version,
            "default_analysis_context_id": default_ctx_id,
        }

        if not lab_type:
            return render(
                request,
                "lims_core/labconfig_wizard/step2.html",
                {
                    "draft": draft,
                    "lab": lab,
                    "form": form_data,
                    "error": "lab_type is required.",
                    "analysis_context_choices": _analysis_context_choices(),
                },
            )

        if not schema_code:
            return render(
                request,
                "lims_core/labconfig_wizard/step2.html",
                {
                    "draft": draft,
                    "lab": lab,
                    "form": form_data,
                    "error": "schema_code is required.",
                    "analysis_context_choices": _analysis_context_choices(),
                },
            )

        payload["laboratory_id"] = lab.id
        payload["profile"] = form_data

        draft.payload = payload
        draft.current_step = 2
        draft.last_error = ""
        draft.save(update_fields=["payload", "current_step", "last_error", "updated_at"])

        return redirect(
            reverse("lims_core:labconfig_wizard:step3", kwargs={"draft_id": draft.id})
        )

    return render(
        request,
        "lims_core/labconfig_wizard/step2.html",
        {
            "draft": draft,
            "lab": lab,
            "form": form_data,
            "analysis_context_choices": _analysis_context_choices(),
        },
    )


@login_required
def step3(request, draft_id: int):
    _require_staff(request)

    try:
        draft = _draft_for_user_or_404(request=request, draft_id=draft_id)
        payload = draft.payload or {}
        lab_id = payload.get("laboratory_id") or draft.laboratory_id
        if not lab_id:
            return redirect(reverse("lims_core:labconfig_wizard:step1"))

        lab = get_object_or_404(Laboratory, pk=int(lab_id))
        profile = LaboratoryProfile.objects.filter(laboratory=lab).first()

        existing = _existing_assignments(profile)

        draft_assignments = payload.get("assignments")
        if isinstance(draft_assignments, list):
            existing = {}
            for r in draft_assignments:
                try:
                    pid = int(r.get("pack_id"))
                except Exception:
                    continue
                existing[pid] = {
                    "is_enabled": bool(r.get("is_enabled", True)),
                    "priority": int(r.get("priority") or 0),
                }

        show_all = (request.GET.get("show_all_packs") or "").strip() in (
            "1",
            "true",
            "yes",
            "on",
        )
        packs = _packs_for_lab(lab, show_all=show_all)

        if request.method == "POST":
            assignments = []
            for p in packs:
                enabled = (request.POST.get(f"pack_{p.id}_enabled") or "") in (
                    "1",
                    "true",
                    "on",
                    "yes",
                )
                priority_raw = (request.POST.get(f"pack_{p.id}_priority") or "").strip()
                try:
                    priority = int(priority_raw or 0)
                except Exception:
                    priority = 0

                if enabled or priority:
                    assignments.append(
                        {
                            "pack_id": int(p.id),
                            "is_enabled": bool(enabled),
                            "priority": int(priority),
                        }
                    )

            payload["assignments"] = assignments
            draft.payload = payload
            draft.current_step = 3
            draft.last_error = ""
            draft.save(update_fields=["payload", "current_step", "last_error", "updated_at"])

            return redirect(
                reverse("lims_core:labconfig_wizard:step4", kwargs={"draft_id": draft.id})
            )

        rows = []
        for p in packs:
            st = existing.get(int(p.id), {})
            rows.append(
                {
                    "pack": p,
                    "enabled": bool(st.get("is_enabled", False)),
                    "priority": int(st.get("priority", 0) or 0),
                }
            )

        return render(
            request,
            "lims_core/labconfig_wizard/step3.html",
            {"draft": draft, "lab": lab, "rows": rows, "show_all": show_all},
        )

    except Exception:
        logger.exception(
            "labconfig step3 failed draft_id=%s user_id=%s",
            draft_id,
            getattr(request.user, "id", None),
        )
        raise


@login_required
def step4(request, draft_id: int):
    _require_staff(request)

    try:
        draft = _draft_for_user_or_404(request=request, draft_id=draft_id)
        payload = draft.payload or {}
        lab_id = payload.get("laboratory_id") or draft.laboratory_id
        if not lab_id:
            return redirect(reverse("lims_core:labconfig_wizard:step1"))

        lab = get_object_or_404(Laboratory, pk=int(lab_id))

        profile_block = payload.get("profile") or {}
        assignments = payload.get("assignments") or []

        pack_ids = []
        for a in assignments:
            try:
                pack_ids.append(int(a.get("pack_id")))
            except Exception:
                continue

        packs = {
            p.id: p
            for p in ConfigPack.objects.filter(id__in=pack_ids).order_by("id")
        }

        assignment_rows = []
        for a in assignments:
            try:
                pid = int(a.get("pack_id"))
            except Exception:
                continue
            p = packs.get(pid)
            assignment_rows.append(
                {
                    "pack_id": pid,
                    "enabled": bool(a.get("is_enabled", True)),
                    "priority": int(a.get("priority") or 0),
                    "kind": getattr(p, "kind", "") if p else "",
                    "code": getattr(p, "code", "") if p else str(pid),
                    "name": getattr(p, "name", "") if p else "",
                }
            )

        if request.method == "POST":
            try:
                apply_labconfig_draft(draft=draft, user=request.user)

                # Kill the draft so the system never "resumes junk" later.
                LabConfigDraft.objects.filter(id=draft.id).delete()

                messages.success(request, f"Configuration applied to {lab.code}.")
                return redirect(
                    reverse("lims_core:labconfig_wizard:success", kwargs={"lab_id": lab.id})
                )

            except Exception as e:
                draft.last_error = str(e)
                draft.save(update_fields=["last_error", "updated_at"])
                return render(
                    request,
                    "lims_core/labconfig_wizard/step4.html",
                    {
                        "draft": draft,
                        "lab": lab,
                        "profile": profile_block,
                        "assignment_rows": assignment_rows,
                        "error": str(e),
                    },
                )

        return render(
            request,
            "lims_core/labconfig_wizard/step4.html",
            {
                "draft": draft,
                "lab": lab,
                "profile": profile_block,
                "assignment_rows": assignment_rows,
                "error": (draft.last_error or "").strip() or None,
            },
        )

    except Exception:
        logger.exception(
            "labconfig step4 failed draft_id=%s user_id=%s",
            getattr(request.user, "id", None),
        )
        raise


@login_required
def success(request, lab_id: int):
    """
    Post-apply landing page. This is the natural next screen after configuration.
    """
    _require_staff(request)

    lab = get_object_or_404(Laboratory, pk=int(lab_id))
    profile = LaboratoryProfile.objects.filter(laboratory=lab).first()

    assignments = []
    if profile:
        fk_field = _assignment_fk_field()
        if fk_field:
            qs = (
                LabPackAssignment.objects.filter(**{fk_field: profile})
                .select_related("pack")
            )
            if _has_field(LabPackAssignment, "priority"):
                qs = qs.order_by("priority", "pack__kind", "pack__code")
            else:
                qs = qs.order_by("pack__kind", "pack__code", "id")

            for a in qs:
                pack = getattr(a, "pack", None)
                assignments.append(
                    {
                        "enabled": bool(getattr(a, "is_enabled", False)),
                        "priority": int(getattr(a, "priority", 0) or 0),
                        "kind": getattr(pack, "kind", "") if pack else "",
                        "code": getattr(pack, "code", "") if pack else "",
                        "name": getattr(pack, "name", "") if pack else "",
                    }
                )

    return render(
        request,
        "lims_core/labconfig_wizard/success.html",
        {
            "lab": lab,
            "profile": profile,
            "assignments": assignments,
        },
    )
