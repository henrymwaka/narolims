# lims_core/wizard/views.py

from __future__ import annotations

import logging
from functools import lru_cache

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from lims_core.models.core import Laboratory, UserRole, SampleBatch
from lims_core.models.drafts import ProjectDraft
from lims_core.wizard.services import apply_project_draft

logger = logging.getLogger(__name__)


def _user_lab_ids(user) -> list[int]:
    return list(
        UserRole.objects.filter(user=user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )


def _draft_for_user_or_404(*, request, draft_id: int) -> ProjectDraft:
    """
    Draft access rule:
    - creator can access their draft
    - staff/superuser can access any draft
    """
    qs = ProjectDraft.objects.all()
    if not (request.user.is_staff or request.user.is_superuser):
        qs = qs.filter(created_by=request.user)
    return get_object_or_404(qs, pk=draft_id)


def _institutes_from_labs(labs_qs):
    """
    Returns a stable list of institutes present in labs_qs, without importing the Institute model.
    """
    rows = (
        labs_qs.values("institute_id", "institute__name")
        .distinct()
        .order_by("institute__name")
    )
    out = []
    for r in rows:
        if r.get("institute_id"):
            out.append({"id": r["institute_id"], "name": (r.get("institute__name") or "").strip()})
    return out


@lru_cache(maxsize=8)
def _load_active_wizard_config():
    """
    Read active wizard config from config packs, if available.

    Cached in-process to avoid re-reading YAML on every request.
    Cleared on gunicorn restart/reload.
    """
    from lims_core.config_packs.loader import get_active_pack_code, load_pack_wizard  # type: ignore

    pack_code = (get_active_pack_code() or "default").strip() or "default"
    return load_pack_wizard(pack_code=pack_code)


def _wizard_template_for_step(step_code: str, *, fallback: str) -> str:
    """
    Config-pack hook:
    - Try to load wizard config from the active pack and return template for step_code.
    - Supports object-like and dict-like config/steps.
    - On any failure or missing template, falls back.
    """
    try:
        cfg = _load_active_wizard_config()
    except Exception as e:
        logger.warning("wizard config pack load failed for step=%s; using fallback: %s", step_code, e)
        return fallback

    if isinstance(cfg, dict):
        steps = cfg.get("steps") or []
    else:
        steps = getattr(cfg, "steps", None) or []

    if not steps:
        return fallback

    for s in steps:
        if not s:
            continue

        if isinstance(s, dict):
            code = (s.get("code") or "").strip()
            tmpl = (s.get("template") or "").strip()
        else:
            code = (getattr(s, "code", "") or "").strip()
            tmpl = (getattr(s, "template", "") or "").strip()

        if str(code) == str(step_code) and tmpl:
            return str(tmpl)

    return fallback


def _wizard_title_and_step_title(step_code: str) -> tuple[str, str]:
    """
    Optional UX metadata from config packs:
    Returns (wizard_title, step_title). Falls back to empty strings if unavailable.
    """
    try:
        cfg = _load_active_wizard_config()
    except Exception:
        return ("", "")

    if isinstance(cfg, dict):
        wiz_title = str(cfg.get("title") or "")
        steps = cfg.get("steps") or []
    else:
        wiz_title = str(getattr(cfg, "title", "") or "")
        steps = getattr(cfg, "steps", None) or []

    step_title = ""
    for s in steps:
        if not s:
            continue

        if isinstance(s, dict):
            code = str(s.get("code") or "")
            title = str(s.get("title") or "")
        else:
            code = str(getattr(s, "code", "") or "")
            title = str(getattr(s, "title", "") or "")

        if str(code) == str(step_code):
            step_title = title
            break

    return (wiz_title, step_title)


@login_required
def step1(request):
    template_name = _wizard_template_for_step("step1", fallback="lims_core/wizard/step1.html")
    wizard_title, step_title = _wizard_title_and_step_title("step1")

    lab_ids = _user_lab_ids(request.user)

    if not lab_ids:
        return render(
            request,
            template_name,
            {
                "wizard_title": wizard_title,
                "wizard_step_title": step_title,
                "wizard_step_code": "step1",
                "institutes": [],
                "laboratories": [],
                "inactive_warning": False,
                "error": (
                    "No laboratory scope is assigned to your account. "
                    "Ask an administrator to assign your laboratory role."
                ),
                "form": {
                    "institute_id": "",
                    "laboratory_id": "",
                    "project_name": "",
                    "project_description": "",
                },
            },
        )

    base_qs = Laboratory.objects.select_related("institute").filter(id__in=lab_ids)
    active_qs = base_qs.filter(is_active=True)

    inactive_warning = False
    labs_qs = active_qs
    if not active_qs.exists():
        labs_qs = base_qs
        inactive_warning = True

    labs_qs = labs_qs.order_by("institute__name", "name", "code")

    institutes = _institutes_from_labs(labs_qs)
    if not institutes:
        return render(
            request,
            template_name,
            {
                "wizard_title": wizard_title,
                "wizard_step_title": step_title,
                "wizard_step_code": "step1",
                "institutes": [],
                "laboratories": [],
                "inactive_warning": inactive_warning,
                "error": (
                    "Your account has lab roles, but no institute-linked labs were found. "
                    "Please contact an administrator."
                ),
                "form": {
                    "institute_id": "",
                    "laboratory_id": "",
                    "project_name": "",
                    "project_description": "",
                },
            },
        )

    selected_institute_id = ""
    if len(institutes) == 1:
        selected_institute_id = str(institutes[0]["id"])
    else:
        selected_institute_id = (request.POST.get("institute_id") or "").strip()

    valid_institute_ids = {str(x["id"]) for x in institutes}
    if not selected_institute_id or selected_institute_id not in valid_institute_ids:
        selected_institute_id = str(institutes[0]["id"])

    labs_in_institute = labs_qs.filter(institute_id=int(selected_institute_id))
    if not labs_in_institute.exists():
        for inst in institutes:
            q = labs_qs.filter(institute_id=int(inst["id"]))
            if q.exists():
                selected_institute_id = str(inst["id"])
                labs_in_institute = q
                break

    if request.method == "POST":
        laboratory_id_raw = (request.POST.get("laboratory_id") or "").strip()
        project_name = (request.POST.get("project_name") or "").strip()
        project_description = (request.POST.get("project_description") or "").strip()

        if not project_name:
            return render(
                request,
                template_name,
                {
                    "wizard_title": wizard_title,
                    "wizard_step_title": step_title,
                    "wizard_step_code": "step1",
                    "institutes": institutes,
                    "laboratories": labs_qs,
                    "inactive_warning": inactive_warning,
                    "error": "Project name is required.",
                    "form": {
                        "institute_id": selected_institute_id,
                        "laboratory_id": laboratory_id_raw,
                        "project_name": project_name,
                        "project_description": project_description,
                    },
                },
            )

        try:
            if laboratory_id_raw:
                laboratory_id = int(laboratory_id_raw)
            else:
                first_lab = labs_in_institute.first()
                if not first_lab:
                    raise ValueError("No lab available")
                laboratory_id = int(first_lab.id)
        except Exception:
            first_lab = labs_in_institute.first()
            if not first_lab:
                raise Http404("No laboratory available in your scope")
            laboratory_id = int(first_lab.id)

        if laboratory_id not in lab_ids:
            raise Http404("Laboratory not in scope")

        lab_obj = get_object_or_404(Laboratory.objects.select_related("institute"), pk=laboratory_id)
        if str(lab_obj.institute_id) != str(selected_institute_id):
            raise Http404("Laboratory does not belong to selected institute")

        payload = {
            "institute_id": lab_obj.institute_id,
            "institute_name": getattr(lab_obj.institute, "name", "") if getattr(lab_obj, "institute", None) else "",
            "laboratory_id": laboratory_id,
            "laboratory_code": lab_obj.code,
            "laboratory_name": lab_obj.name,
            "template": {"workflow_code": "DEFAULT", "workflow_name": "Default workflow", "workflow_version": "v1"},
            "project": {"name": project_name, "description": project_description},
            "samples": {"create_placeholders": False, "count": 0, "sample_type": "test"},
        }

        draft = ProjectDraft.objects.create(
            created_by=request.user,
            laboratory_id=laboratory_id,
            payload=payload,
        )

        return redirect(reverse("lims_core:wizard:step2", kwargs={"draft_id": draft.id}))

    preselected_lab_id = ""
    if labs_in_institute.count() == 1:
        preselected_lab_id = str(labs_in_institute.first().id)

    return render(
        request,
        template_name,
        {
            "wizard_title": wizard_title,
            "wizard_step_title": step_title,
            "wizard_step_code": "step1",
            "institutes": institutes,
            "laboratories": labs_qs,
            "inactive_warning": inactive_warning,
            "form": {
                "institute_id": selected_institute_id,
                "laboratory_id": preselected_lab_id,
                "project_name": "",
                "project_description": "",
            },
        },
    )


@login_required
def step2(request, draft_id: int):
    """
    Step 2: confirm sample placeholder creation and apply the draft.

    IMPORTANT:
    apply_project_draft() returns a Project (per tests).
    Older code may return a dict. We support both to keep UI robust.
    """
    template_name = _wizard_template_for_step("step2", fallback="lims_core/wizard/step2.html")
    wizard_title, step_title = _wizard_title_and_step_title("step2")

    draft = _draft_for_user_or_404(request=request, draft_id=draft_id)

    payload = draft.payload or {}
    lab_id = payload.get("laboratory_id") or draft.laboratory_id
    if not lab_id:
        return redirect(reverse("lims_core:wizard:step1"))

    lab_ids = _user_lab_ids(request.user)
    if not (request.user.is_staff or request.user.is_superuser):
        if int(lab_id) not in lab_ids:
            raise Http404("Laboratory not in scope")

    project_block = payload.get("project") or {}
    samples_block = payload.get("samples") or {}

    if request.method == "POST":
        create_placeholders = (request.POST.get("create_placeholders") or "") in ("1", "true", "on", "yes")
        count_raw = (request.POST.get("count") or "0").strip()
        sample_type = (request.POST.get("sample_type") or "test").strip() or "test"

        try:
            count = int(count_raw)
        except Exception:
            count = 0

        if count < 0:
            count = 0
        if count > 5000:
            count = 5000

        payload["samples"] = {
            "create_placeholders": bool(create_placeholders),
            "count": int(count),
            "sample_type": sample_type,
        }

        draft.payload = payload
        draft.last_error = ""
        draft.save(update_fields=["payload", "last_error"])

        try:
            result = apply_project_draft(draft=draft, user=request.user)

            # Support both return shapes
            if isinstance(result, dict):
                project = result.get("project")
                batch = result.get("batch")
            else:
                project = result
                batch = None

            # Prefer the newest intake batch for that project
            if batch is None and project is not None:
                try:
                    batch = (
                        SampleBatch.objects.filter(project=project)
                        .order_by("-created_at", "-id")
                        .first()
                    )
                except Exception:
                    batch = None

            if batch is not None:
                return redirect(f"/lims/ui/batches/{batch.id}/")

            return redirect("/lims/ui/")

        except Exception as e:
            draft.last_error = str(e)
            draft.save(update_fields=["last_error"])

            samples_block = payload.get("samples") or {}
            return render(
                request,
                template_name,
                {
                    "wizard_title": wizard_title,
                    "wizard_step_title": step_title,
                    "wizard_step_code": "step2",
                    "draft": draft,
                    "project": project_block,
                    "samples": samples_block,
                    "error": str(e),
                },
            )

    return render(
        request,
        template_name,
        {
            "wizard_title": wizard_title,
            "wizard_step_title": step_title,
            "wizard_step_code": "step2",
            "draft": draft,
            "project": project_block,
            "samples": samples_block,
            "error": (draft.last_error or "").strip() or None,
        },
    )
