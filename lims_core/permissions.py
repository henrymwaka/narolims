# lims_core/permissions.py
from __future__ import annotations

from typing import Optional

from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied

from .models import Laboratory, UserRole


# ------------------------------------------------------------------
# Role definitions
# ------------------------------------------------------------------
WRITE_ROLES = {"PI", "Lab Manager", "Data Manager", "Technician"}
ADMIN_ROLES = {"PI", "Lab Manager"}


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------
def _parse_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def resolve_current_laboratory(request) -> Optional[Laboratory]:
    """
    Canonical lab resolver used by permissions.

    Priority:
      1) ?lab=<id>
      2) X-Laboratory header
      3) single-lab auto resolution via UserRole
      4) superuser with exactly one active lab
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    lab_id = _parse_int(getattr(request, "query_params", {}).get("lab"))
    if lab_id is None:
        lab_id = _parse_int(getattr(request, "headers", {}).get("X-Laboratory"))

    if lab_id is not None:
        try:
            lab = Laboratory.objects.select_related("institute").get(
                id=lab_id,
                is_active=True,
            )
        except Laboratory.DoesNotExist:
            return None

        if user.is_superuser:
            return lab

        if UserRole.objects.filter(user=user, laboratory=lab).exists():
            return lab

        return None

    labs = list(
        Laboratory.objects.filter(
            is_active=True,
            user_roles__user=user,
        ).distinct()[:2]
    )
    if len(labs) == 1:
        return labs[0]

    if user.is_superuser:
        only = list(Laboratory.objects.filter(is_active=True)[:2])
        if len(only) == 1:
            return only[0]

    return None


def user_has_any_role(user, laboratory: Laboratory, allowed_roles: set[str]) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return UserRole.objects.filter(
        user=user,
        laboratory=laboratory,
        role__in=allowed_roles,
    ).exists()


# ------------------------------------------------------------------
# Permission class
# ------------------------------------------------------------------
class IsRoleAllowedOrReadOnly(BasePermission):
    """
    Read: any authenticated user
    Write: requires role in active laboratory

    Lab resolved via:
      ?lab=<id> or X-Laboratory header
      else single-lab auto resolution
    """

    message = (
        "Write access denied. Provide ?lab=<id> or X-Laboratory header "
        "and ensure you have an appropriate role."
    )

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        # Global models (Institute, Laboratory) are superuser-only
        model = getattr(getattr(view, "queryset", None), "model", None)
        if model in {Laboratory,}:
            return bool(user.is_superuser)

        lab = resolve_current_laboratory(request)
        if not lab:
            raise PermissionDenied(self.message)

        return user_has_any_role(user, lab, WRITE_ROLES)

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        if user.is_superuser:
            return True

        # ----------------------------------------------------------
        # StaffMember requires ADMIN roles (priority case)
        # ----------------------------------------------------------
        if obj.__class__.__name__ == "StaffMember":
            staff_lab = getattr(obj, "laboratory", None)
            if staff_lab:
                return user_has_any_role(user, staff_lab, ADMIN_ROLES)

            staff_inst = getattr(obj, "institute", None)
            if staff_inst:
                return UserRole.objects.filter(
                    user=user,
                    laboratory__institute=staff_inst,
                    role__in=ADMIN_ROLES,
                    laboratory__is_active=True,
                ).exists()

            return False

        # ----------------------------------------------------------
        # Generic lab-scoped objects
        # ----------------------------------------------------------
        obj_lab = getattr(obj, "laboratory", None)
        if obj_lab:
            return user_has_any_role(user, obj_lab, WRITE_ROLES)

        return False
