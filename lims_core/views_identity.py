# lims_core/views_identity.py
from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import UserRole


class WhoAmIView(APIView):
    """
    Returns the currently authenticated user and their roles (scoped by laboratory).

    This is meant for the browser widget to:
      - confirm session auth is working
      - show roles
      - optionally filter transitions client-side
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        roles_qs = (
            UserRole.objects
            .filter(user=user)
            .select_related("laboratory")
            .order_by("laboratory__id", "role")
        )

        roles = [
            {
                "laboratory_id": ur.laboratory_id,
                "laboratory": str(ur.laboratory) if ur.laboratory else None,
                "role": ur.role,
            }
            for ur in roles_qs
        ]

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "is_superuser": bool(getattr(user, "is_superuser", False)),
                "roles": roles,
            }
        )
