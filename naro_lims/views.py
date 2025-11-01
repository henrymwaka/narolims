from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema


class HomeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="home",
        summary="API landing",
        description="Landing page for NARO-LIMS API with links to useful endpoints.",
        responses={200: dict},
        tags=["System"],
    )
    def get(self, request):
        return Response({
            "message": "Welcome to NARO-LIMS API",
            "endpoints": {
                "admin": "/admin/",
                "token_obtain": "/api/token/",
                "token_refresh": "/api/token/refresh/",
                "schema": "/api/schema/",
                "docs": "/api/docs/",
                "redoc": "/api/redoc/",
                "health": "/lims/health/"
            }
        })
