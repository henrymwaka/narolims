# UI contract: docs/NARO-LIMS_UI_and_Template_Contract.md
# lims_core/views_ui.py

from __future__ import annotations

import traceback
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from .models.core import (
    Sample,
    Experiment,
    UserRole,
    SampleBatch,
    Project,
    Laboratory,
)
from .workflows import workflow_definition

# Laboratory configuration selector (single source of truth)
from .labs.selectors import get_lab_profile_for_object

# Metadata enforcement (shared with workflow runtime)
from lims_core.workflows.metadata_gating import check_metadata_gate


# ------------------------------------------------------------
# Optional SLA runtime helper
# ------------------------------------------------------------
try:
    from .workflows.runtime_sla import compute_runtime_sla
except Exception:
    compute_runtime_sla = None


# ============================================================
# UI scope helpers
# ============================================================

def _user_lab_ids(user) -> list[int]:
    return list(
        UserRole.objects.filter(user=user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )


def _require_lab_in_scope(*, user, laboratory_id: int) -> None:
    """
    Enforce that a non-staff user can only operate within assigned lab scope.
    Staff and superusers are allowed.
    """
    if user.is_staff or user.is_superuser:
        return
    lab_ids = _user_lab_ids(user)
    if int(laboratory_id) not in [int(x) for x in lab_ids]:
        raise Http404("Laboratory not in scope")


def _require_project_in_scope(*, user, project: Project) -> None:
    """
    Project scope is derived from project.laboratory.
    """
    if not project.laboratory_id:
        raise Http404("Project has no laboratory assigned")
    _require_lab_in_scope(user=user, laboratory_id=int(project.laboratory_id))


def _user_has_active_projects_in_scope(user, *, lab_ids: list[int] | None = None) -> bool:
    """
    True if the user has at least one ACTIVE project in their lab scope.
    Uses provided lab_ids when available to avoid repeated queries.
    """
    if lab_ids is None:
        lab_ids = _user_lab_ids(user)
    if not lab_ids:
        return False

    return Project.objects.filter(
        laboratory_id__in=lab_ids,
        is_active=True,
    ).exists()


def _wizard_step1_redirect():
    """
    Safe redirect to wizard step 1.
    Uses URL reversing when possible, falls back to the canonical path.
    """
    try:
        return redirect(reverse("lims_core:wizard:step1"))
    except Exception:
        return redirect("/lims/wizard/step-1/")


# ============================================================
# Metadata helpers (UI-safe)
# ============================================================

def _get_metadata_status(*, laboratory, object_type: str, object_id: int) -> dict:
    """
    UI-safe metadata completeness summary.

    Returns:
    {
        "complete": bool,
        "missing": int,
        "invalid": int,
    }
    """
    gate = check_metadata_gate(
        laboratory=laboratory,
        object_type=object_type,
        object_id=object_id,
    )

    missing = len(gate.get("missing_fields", []))
    invalid = len(gate.get("invalid_fields", []))

    return {
        "complete": gate["allowed"],
        "missing": missing,
        "invalid": invalid,
    }


# ============================================================
# Public site content
# ============================================================

FEATURES = [
    {
        "slug": "samples",
        "name": "Samples",
        "tag": "Active",
        "summary": "Register, track, and audit sample lifecycle across laboratory workflows.",
        "bullets": [
            "Sample registration and identifiers",
            "Status transitions with audit trail",
            "Lab-scoped queues and filtering",
        ],
        "cta_label": "Open Samples",
        "cta_href": "/lims/ui/samples/",
    },
    {
        "slug": "workflows",
        "name": "Workflow Engine",
        "tag": "Active",
        "summary": "Role-aware transitions, permissions validation, and traceable timelines.",
        "bullets": [
            "Allowed transitions per role",
            "Bulk workflow updates",
            "Timeline and history endpoints",
        ],
        "cta_label": "Workflow Demo",
        "cta_href": "/lims/ui/workflow-demo/",
    },
    {
        "slug": "inventory",
        "name": "Inventory",
        "tag": "Admin-first",
        "summary": "Inventory items, stock traceability, and consumption tracking.",
        "bullets": [
            "Item master data in admin",
            "Stock and usage readiness",
            "Foundation for procurement traceability",
        ],
        "cta_label": "Open Admin",
        "cta_href": "/admin/",
    },
    {
        "slug": "audit",
        "name": "Audit and Compliance",
        "tag": "Core",
        "summary": "Audit-ready operations with logs, role mapping, and traceable actions.",
        "bullets": [
            "Audit logs API",
            "Role-to-lab scoping",
            "Compliance-friendly workflow events",
        ],
        "cta_label": "Identity Check",
        "cta_href": "/lims/whoami/",
    },
]


def _read_repo_file(relpath: str, max_chars: int = 200_000) -> str:
    try:
        base = Path(__file__).resolve().parent.parent
        p = (base / relpath).resolve()
        if not str(p).startswith(str(base)):
            return ""
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def landing(request):
    # Logged-in users should not see marketing landing. Route into workspace entry.
    if getattr(request, "user", None) and request.user.is_authenticated:
        return redirect("lims_core:ui-home")

    return render(request, "lims_core/landing.html", {"features": FEATURES[:4]})


def features(request):
    return render(request, "lims_core/features.html", {"features": FEATURES})


def feature_detail(request, slug: str):
    item = next((x for x in FEATURES if x["slug"] == slug), None)
    if not item:
        raise Http404("Feature not found")
    return render(request, "lims_core/feature_detail.html", {"feature": item})


def updates(request):
    changelog = _read_repo_file("docs/CHANGELOG_NARO-LIMS_UI.md")
    return render(request, "lims_core/updates.html", {"changelog_text": changelog})


def docs_hub(request):
    return render(request, "lims_core/docs_hub.html")


# ============================================================
# Authenticated UI
# ============================================================

def ui_logout(request):
    next_url = request.GET.get("next") or "/lims/"
    auth_logout(request)
    return redirect(next_url)


@login_required
def home(request):
    """
    Workspace entry point.

    If there is no ACTIVE project in the user's lab scope:
      - by default, guide them into the wizard
      - allow override via ?skip_wizard=1
    Also exposes wizard_first to enable an empty-state card in the workspace template.
    """
    lab_ids: list[int] = []
    wizard_first = False

    try:
        lab_ids = _user_lab_ids(request.user)
        has_active = _user_has_active_projects_in_scope(request.user, lab_ids=lab_ids)

        # "wizard_first" means: user has lab scope but no active project exists yet
        wizard_first = bool(lab_ids) and (not has_active)

        if request.GET.get("skip_wizard") != "1" and wizard_first:
            return _wizard_step1_redirect()

    except Exception:
        # Never block the user if scope logic fails
        wizard_first = False

    return render(
        request,
        "lims_core/home.html",
        {
            "username": getattr(request.user, "username", ""),
            "wizard_first": wizard_first,
        },
    )


@login_required
def ui_stats(request):
    lab_ids = list(
        UserRole.objects.filter(user=request.user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )

    lab_id = None
    if lab_ids:
        try:
            lab_id = int(request.GET.get("lab") or lab_ids[0])
        except Exception:
            lab_id = lab_ids[0]

    payload = {
        "ok": True,
        "lab_id": lab_id or "",
        "available_labs": lab_ids,
        "stats": {},
    }

    try:
        qs = Sample.objects.all()
        if lab_id:
            qs = qs.filter(Q(laboratory_id=lab_id) | Q(project__laboratory_id=lab_id))
        payload["stats"]["samples_total"] = qs.count()
    except Exception:
        payload["stats"]["samples_total"] = None

    try:
        qs = Experiment.objects.all()
        if lab_id:
            qs = qs.filter(laboratory_id=lab_id)
        payload["stats"]["experiments_total"] = qs.count()
    except Exception:
        payload["stats"]["experiments_total"] = None

    return JsonResponse(payload)


@login_required
def workflow_widget_demo(request):
    return render(
        request,
        "lims_core/workflow_widget.html",
        {"workflow_kind": "sample", "workflow_object_id": 1},
    )


# ============================================================
# Samples
# ============================================================

@login_required
def sample_list(request):
    try:
        lab_ids = list(
            UserRole.objects.filter(user=request.user)
            .values_list("laboratory_id", flat=True)
            .distinct()
        )

        lab_id = None
        if lab_ids:
            try:
                lab_id = int(request.GET.get("lab") or lab_ids[0])
            except Exception:
                lab_id = lab_ids[0]

        qs = Sample.objects.select_related("project", "batch").order_by("-id")

        if lab_id:
            qs = qs.filter(Q(laboratory_id=lab_id) | Q(project__laboratory_id=lab_id))

        qs = qs[:500]

        for s in qs:
            if compute_runtime_sla:
                try:
                    s._sla = compute_runtime_sla(
                        kind="sample",
                        obj=s,
                        current_status=s.status,
                    )
                except Exception:
                    s._sla = None
            else:
                s._sla = None

        try:
            wf = workflow_definition("sample")
            statuses = wf.get("statuses", [])
        except Exception:
            statuses = []

        return render(
            request,
            "lims_core/samples/list.html",
            {
                "samples": qs,
                "lab_id": lab_id or "",
                "available_labs": lab_ids,
                "workflow_statuses": statuses,
            },
        )

    except Exception:
        tb = traceback.format_exc()
        print("\n[SAMPLE_LIST_500]\n" + tb, flush=True)

        if request.GET.get("trace") == "1":
            return HttpResponse(
                "<h1>/lims/ui/samples/ crashed</h1><pre>" + tb + "</pre>",
                status=500,
            )
        raise


@login_required
def sample_detail(request, pk: int):
    try:
        sample = get_object_or_404(Sample, pk=pk)

        # enforce scope
        if sample.project and sample.project.laboratory_id:
            _require_lab_in_scope(user=request.user, laboratory_id=int(sample.project.laboratory_id))

        sla = None
        if compute_runtime_sla:
            try:
                sla = compute_runtime_sla(
                    kind="sample",
                    obj=sample,
                    current_status=sample.status,
                )
            except Exception:
                sla = None

        # This selector must never be allowed to crash the detail page
        lab_profile = None
        try:
            lab_profile = get_lab_profile_for_object(sample)
        except Exception:
            lab_profile = None

        metadata_status = None
        if sample.laboratory:
            metadata_status = _get_metadata_status(
                laboratory=sample.laboratory,
                object_type="sample",
                object_id=sample.id,
            )

        return render(
            request,
            "lims_core/samples/detail.html",
            {
                "sample": sample,
                "sla": sla,
                "lab_profile": lab_profile,
                "metadata_status": metadata_status,
            },
        )

    except Exception:
        tb = traceback.format_exc()
        print("\n[SAMPLE_DETAIL_500]\n" + tb, flush=True)

        if request.GET.get("trace") == "1":
            return HttpResponse(
                "<h1>/lims/ui/samples/%s/ crashed</h1><pre>%s</pre>" % (pk, tb),
                status=500,
            )
        raise


# ============================================================
# Experiments
# ============================================================

@login_required
def experiment_detail(request, pk: int):
    try:
        experiment = get_object_or_404(Experiment, pk=pk)

        # enforce scope via project lab
        if experiment.project and experiment.project.laboratory_id:
            _require_lab_in_scope(user=request.user, laboratory_id=int(experiment.project.laboratory_id))

        # This selector must never be allowed to crash the detail page
        lab_profile = None
        try:
            lab_profile = get_lab_profile_for_object(experiment)
        except Exception:
            lab_profile = None

        metadata_status = None
        if experiment.laboratory:
            metadata_status = _get_metadata_status(
                laboratory=experiment.laboratory,
                object_type="experiment",
                object_id=experiment.id,
            )

        return render(
            request,
            "lims_core/experiments/detail.html",
            {
                "experiment": experiment,
                "lab_profile": lab_profile,
                "metadata_status": metadata_status,
            },
        )

    except Exception:
        tb = traceback.format_exc()
        print("\n[EXPERIMENT_DETAIL_500]\n" + tb, flush=True)

        if request.GET.get("trace") == "1":
            return HttpResponse(
                "<h1>/lims/ui/experiments/%s/ crashed</h1><pre>%s</pre>" % (pk, tb),
                status=500,
            )
        raise


# ============================================================
# Batches (canonical intake container)
# ============================================================

@login_required
def batch_list(request):
    lab_ids = list(
        UserRole.objects.filter(user=request.user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )

    qs = (
        SampleBatch.objects
        .select_related("project", "laboratory")
        .prefetch_related("samples")
        .order_by("-created_at")
    )

    if lab_ids and not (request.user.is_staff or request.user.is_superuser):
        qs = qs.filter(laboratory_id__in=lab_ids)

    for b in qs:
        b.sample_count = b.samples.count()

    return render(
        request,
        "lims_core/batches/list.html",
        {
            "batches": qs,
            "available_labs": lab_ids,
        },
    )


@login_required
def batch_create(request):
    """
    Coherent rule:
    - A batch is created for a project
    - Laboratory is derived from the project (never trusted from POST)
    - Scope check is enforced using project.laboratory
    """
    lab_ids = _user_lab_ids(request.user)

    laboratories = Laboratory.objects.filter(id__in=lab_ids)
    projects = Project.objects.filter(laboratory_id__in=lab_ids)

    if request.method == "POST":
        project_id_raw = (request.POST.get("project") or "").strip()
        if not project_id_raw:
            return render(
                request,
                "lims_core/batches/create.html",
                {
                    "laboratories": laboratories,
                    "projects": projects,
                    "error": "Project is required",
                },
            )

        project = get_object_or_404(Project, pk=int(project_id_raw))
        _require_project_in_scope(user=request.user, project=project)

        # Derive laboratory from project to prevent mismatches
        if not project.laboratory_id:
            return render(
                request,
                "lims_core/batches/create.html",
                {
                    "laboratories": laboratories,
                    "projects": projects,
                    "error": "Selected project has no laboratory assigned.",
                },
            )

        batch_code = (request.POST.get("batch_code") or "").strip()
        if not batch_code:
            # Safe default. You can make this smarter later (lab code, date, seq).
            batch_code = "BATCH-%s" % timezone.now().strftime("%Y%m%d-%H%M%S")

        batch = SampleBatch.objects.create(
            laboratory_id=project.laboratory_id,
            project_id=project.id,
            batch_code=batch_code,
            collected_at=request.POST.get("collected_at") or None,
            collected_by=(request.POST.get("collected_by") or "").strip(),
            collection_site=(request.POST.get("collection_site") or "").strip(),
            client_name=(request.POST.get("client_name") or "").strip(),
            notes=(request.POST.get("notes") or "").strip(),
        )
        return redirect(f"/lims/ui/batches/{batch.id}/")

    return render(
        request,
        "lims_core/batches/create.html",
        {
            "laboratories": laboratories,
            "projects": projects,
        },
    )


@login_required
def batch_detail(request, pk: int):
    batch = get_object_or_404(SampleBatch, pk=pk)

    # enforce scope
    if batch.laboratory_id:
        _require_lab_in_scope(user=request.user, laboratory_id=int(batch.laboratory_id))

    samples = batch.samples.order_by("sample_id")

    lab_profile = None
    try:
        lab_profile = get_lab_profile_for_object(batch)
    except Exception:
        lab_profile = None

    return render(
        request,
        "lims_core/batches/detail.html",
        {
            "batch": batch,
            "samples": samples,
            "lab_profile": lab_profile,
        },
    )


@login_required
def sample_bulk_register(request, batch_id: int):
    """
    Coherent rule:
    - Samples are created inside a batch
    - If sample_id is blank, the Sample model generates a compliant ID
    - Scope check is enforced using batch.laboratory
    """
    batch = get_object_or_404(SampleBatch, pk=batch_id)

    if batch.laboratory_id:
        _require_lab_in_scope(user=request.user, laboratory_id=int(batch.laboratory_id))

    if request.method == "POST":
        sample_ids = request.POST.getlist("sample_id")
        names = request.POST.getlist("name")
        types = request.POST.getlist("sample_type")

        created = 0
        for i in range(max(len(sample_ids), len(names), len(types))):
            sid = sample_ids[i] if i < len(sample_ids) else ""
            nm = names[i] if i < len(names) else ""
            st = types[i] if i < len(types) else ""

            if not (sid or nm or st):
                continue

            Sample.objects.create(
                laboratory=batch.laboratory,
                project=batch.project,
                batch=batch,
                sample_id=(sid or ""),      # allow blank, model will generate a unique ID
                name=(nm or "").strip(),
                sample_type=(st or "").strip(),
                status="REGISTERED",
            )
            created += 1

        return redirect(f"/lims/ui/batches/{batch.id}/")

    return render(
        request,
        "lims_core/samples/bulk_register.html",
        {"batch": batch},
    )
