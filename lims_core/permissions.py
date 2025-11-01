# lims_core/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import UserRole

# Adjust the set to match your lab’s roles
ALLOWED_ROLES_FOR_WRITE = {"PI", "Lab Manager", "Data Manager", "Manager"}


def user_has_any_role(user, roles=ALLOWED_ROLES_FOR_WRITE):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    return UserRole.objects.filter(user=user, role__in=roles).exists()


class IsRoleAllowedOrReadOnly(BasePermission):
    """
    Read (GET/HEAD/OPTIONS): any authenticated user.
    Write (POST/PUT/PATCH/DELETE): superuser or user with an allowed role.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return user_has_any_role(request.user)
