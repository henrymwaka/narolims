"""URL configuration for NARO-LIMS project."""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.conf.urls.static import static

from .views import LandingView, ApiHomeView

urlpatterns = [
    # Public landing page
    path("", LandingView.as_view(), name="landing"),

    # API landing (JSON)
    path("api/", ApiHomeView.as_view(), name="api-home"),

    # Admin
    path("admin/", admin.site.urls),

    # Authentication (JWT + browsable API login)
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/", include("rest_framework.urls")),

    # OpenAPI schema and docs
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="redoc",
    ),

    # LIMS app endpoints
    path("lims/", include("lims_core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
