# lims_core/views_ui_lab_admin.py

from __future__ import annotations

import logging
import secrets
import string
from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from lims_core.models.core import Laboratory, UserRole

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Helpers (kept local so you do not couple wizard internals here)
# -------------------------------------------------------------------
def _model_field_names(model) -> set[str]:
    try:
        return {f.name for f in model._meta.get_fields()}
    except Exception:
        return set()


def _has_field(model, name: str) -> bool:
    return name in _model_field_names(model)


def _user_lab_ids(user) -> list[int]:
    """
    Source of truth: UserRole scoped labs, unless superuser.
    """
    if getattr(user, "is_superuser", False):
        return list(Laboratory.objects.values_list("id", flat=True))
    return list(
        UserRole.objects.filter(user=user)
        .values_list("laboratory_id", flat=True)
        .distinct()
    )


def _require_lab_admin_access(request) -> None:
    """
    Allow:
      - superuser/staff
      - OR a normal user who has a 'role' that looks like manager/admin in at least one lab.
    This keeps lab managers usable without forcing Django staff.

    If your role model differs, you can harden this later.
    """
    if request.user.is_superuser or request.user.is_staff:
        return

    # Must have lab scope at minimum
    if not UserRole.objects.filter(user=request.user).exists():
        raise Http404("Not permitted")

    # If UserRole has a role-like field, allow manager/admin-ish roles
    role_field = None
    for cand in ("role", "role_code", "role_name", "name"):
        if _has_field(UserRole, cand):
            role_field = cand
            break

    if not role_field:
        # No way to detect role permissions reliably, keep locked down
        raise Http404("Not permitted")

    qs = UserRole.objects.filter(user=request.user)
    allowed = False
    for ur in qs[:50]:
        raw = (getattr(ur, role_field, "") or "").strip().lower()
        if "manager" in raw or "admin" in raw or raw in ("lab_manager", "institute_admin"):
            allowed = True
            break

    if not allowed:
        raise Http404("Not permitted")


def _userrole_role_choices() -> list[tuple[str, str]]:
    """
    Read choices from the model field if present, else fallback.
    """
    try:
        if not _has_field(UserRole, "role"):
            return [
                ("lab_user", "Lab user"),
                ("lab_manager", "Lab manager"),
            ]
        f = UserRole._meta.get_field("role")
        choices = getattr(f, "choices", None) or []
        out = []
        for c in choices:
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                out.append((str(c[0]), str(c[1])))
        return out or [
            ("lab_user", "Lab user"),
            ("lab_manager", "Lab manager"),
        ]
    except Exception:
        return [
            ("lab_user", "Lab user"),
            ("lab_manager", "Lab manager"),
        ]


def _random_temp_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(max(10, int(length or 14))))


# -------------------------------------------------------------------
# Views
# -------------------------------------------------------------------
@login_required
def lab_admin_home(request):
    _require_lab_admin_access(request)

    lab_ids = _user_lab_ids(request.user)
    labs = Laboratory.objects.filter(id__in=lab_ids).order_by("name", "code", "id")

    # Pull user assignments for these labs
    urs = (
        UserRole.objects.filter(laboratory_id__in=lab_ids)
        .select_related("user", "laboratory")
        .order_by("laboratory__name", "user__username", "id")
    )

    # Group by lab
    by_lab: dict[int, dict[str, Any]] = {}
    for lab in labs:
        by_lab[lab.id] = {"lab": lab, "rows": []}

    # Detect best role field to display
    role_field = None
    for cand in ("role", "role_code", "role_name", "name"):
        if _has_field(UserRole, cand):
            role_field = cand
            break

    for ur in urs:
        lab = getattr(ur, "laboratory", None)
        user = getattr(ur, "user", None)
        if not lab or not user:
            continue

        role_val = ""
        if role_field:
            role_val = (getattr(ur, role_field, "") or "").strip()

        by_lab.setdefault(lab.id, {"lab": lab, "rows": []})
        by_lab[lab.id]["rows"].append(
            {
                "username": getattr(user, "username", ""),
                "email": getattr(user, "email", ""),
                "is_active": bool(getattr(user, "is_active", False)),
                "is_staff": bool(getattr(user, "is_staff", False)),
                "last_login": getattr(user, "last_login", None),
                "role": role_val,
                "user_id": getattr(user, "id", None),
                "ur_id": getattr(ur, "id", None),
            }
        )

    groups = [by_lab[k] for k in sorted(by_lab.keys())]

    return render(
        request,
        "lims_core/lab_admin/index.html",
        {
            "groups": groups,
            "lab_count": labs.count(),
            "role_field": role_field or "",
        },
    )


@login_required
def lab_admin_create_user(request):
    _require_lab_admin_access(request)

    lab_ids = _user_lab_ids(request.user)
    labs = Laboratory.objects.filter(id__in=lab_ids).order_by("name", "code", "id")

    User = get_user_model()

    # Optional: if you want to restrict who can create users, enforce staff/superuser only here.
    # For now we allow lab admins.
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()

        # Optional assignment on create
        lab_id_raw = (request.POST.get("laboratory_id") or "").strip()
        role = (request.POST.get("role") or "").strip()

        if not username:
            return render(
                request,
                "lims_core/lab_admin/create_user.html",
                {
                    "labs": labs,
                    "roles": _userrole_role_choices(),
                    "error": "Username is required.",
                    "form": {
                        "username": username,
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "laboratory_id": lab_id_raw,
                        "role": role,
                    },
                },
            )

        if User.objects.filter(username=username).exists():
            return render(
                request,
                "lims_core/lab_admin/create_user.html",
                {
                    "labs": labs,
                    "roles": _userrole_role_choices(),
                    "error": "That username already exists.",
                    "form": {
                        "username": username,
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "laboratory_id": lab_id_raw,
                        "role": role,
                    },
                },
            )

        temp_password = _random_temp_password()

        try:
            with transaction.atomic():
                user = User.objects.create(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                )
                user.set_password(temp_password)
                user.save()

                # Optional lab assignment
                if lab_id_raw:
                    try:
                        lab_id = int(lab_id_raw)
                    except Exception:
                        lab_id = None

                    if lab_id and lab_id in lab_ids:
                        lab = Laboratory.objects.get(id=lab_id)

                        ur_kwargs = {"user": user, "laboratory": lab}
                        defaults = {}

                        if _has_field(UserRole, "role") and role:
                            defaults["role"] = role

                        ur, created = UserRole.objects.get_or_create(
                            **ur_kwargs, defaults=defaults
                        )
                        if not created and _has_field(UserRole, "role") and role:
                            setattr(ur, "role", role)
                            ur.save(update_fields=["role"])

        except Exception:
            logger.exception("Failed creating lab user")
            return render(
                request,
                "lims_core/lab_admin/create_user.html",
                {
                    "labs": labs,
                    "roles": _userrole_role_choices(),
                    "error": "Failed to create user. Check logs.",
                    "form": {
                        "username": username,
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "laboratory_id": lab_id_raw,
                        "role": role,
                    },
                },
            )

        messages.success(
            request,
            f"User '{username}' created. Temporary password: {temp_password}",
        )
        return redirect(reverse("lims_core:lab-admin-home"))

    return render(
        request,
        "lims_core/lab_admin/create_user.html",
        {"labs": labs, "roles": _userrole_role_choices()},
    )


@login_required
def lab_admin_assign_user(request):
    _require_lab_admin_access(request)

    lab_ids = _user_lab_ids(request.user)
    labs = Laboratory.objects.filter(id__in=lab_ids).order_by("name", "code", "id")

    User = get_user_model()

    # Users list: keep it practical, do not load huge datasets
    users = User.objects.all().order_by("username")[:5000]

    if request.method == "POST":
        user_id_raw = (request.POST.get("user_id") or "").strip()
        lab_id_raw = (request.POST.get("laboratory_id") or "").strip()
        role = (request.POST.get("role") or "").strip()

        try:
            user_id = int(user_id_raw)
        except Exception:
            user_id = None

        try:
            lab_id = int(lab_id_raw)
        except Exception:
            lab_id = None

        if not user_id:
            return render(
                request,
                "lims_core/lab_admin/assign_user.html",
                {
                    "labs": labs,
                    "roles": _userrole_role_choices(),
                    "users": users,
                    "error": "Select a user.",
                },
            )

        if not lab_id or lab_id not in lab_ids:
            return render(
                request,
                "lims_core/lab_admin/assign_user.html",
                {
                    "labs": labs,
                    "roles": _userrole_role_choices(),
                    "users": users,
                    "error": "Select a laboratory in your scope.",
                },
            )

        user = get_object_or_404(User, pk=user_id)
        lab = get_object_or_404(Laboratory, pk=lab_id)

        try:
            with transaction.atomic():
                defaults = {}
                if _has_field(UserRole, "role") and role:
                    defaults["role"] = role

                ur, created = UserRole.objects.get_or_create(
                    user=user,
                    laboratory=lab,
                    defaults=defaults,
                )

                if not created and _has_field(UserRole, "role") and role:
                    setattr(ur, "role", role)
                    ur.save(update_fields=["role"])

        except Exception:
            logger.exception("Failed assigning user to lab")
            return render(
                request,
                "lims_core/lab_admin/assign_user.html",
                {
                    "labs": labs,
                    "roles": _userrole_role_choices(),
                    "users": users,
                    "error": "Failed to assign user. Check logs.",
                },
            )

        messages.success(
            request,
            f"Assigned '{user.username}' to {lab.code}.",
        )
        return redirect(reverse("lims_core:lab-admin-home"))

    return render(
        request,
        "lims_core/lab_admin/assign_user.html",
        {"labs": labs, "roles": _userrole_role_choices(), "users": users},
    )
