from django.views.generic import TemplateView
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response


class LandingView(TemplateView):
    template_name = "lims_core/landing.html"

    def dispatch(self, request, *args, **kwargs):
        # If already signed in, send user to the real app home
        if request.user.is_authenticated:
            return redirect("/lims/ui/")
        return super().dispatch(request, *args, **kwargs)


class ApiHomeView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                "message": "Welcome to NARO-LIMS API",
                "endpoints": {
                    "admin": "/admin/",
                    "token_obtain": "/api/token/",
                    "token_refresh": "/api/token/refresh/",
                    "schema": "/api/schema/",
                    "swagger": "/api/schema/swagger-ui/",
                    "redoc": "/api/schema/redoc/",
                    "health": "/lims/health/",
                },
            }
        )
