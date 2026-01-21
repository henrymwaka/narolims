# lims_core/labconfig_wizard/urls.py

from django.urls import path
from . import views

app_name = "labconfig_wizard"

urlpatterns = [
    # /lims/labconfig/ and /lims/labconfig/manage/
    path("", views.manage, name="manage"),
    path("manage/", views.manage, name="manage2"),

    path("create-lab/", views.create_lab, name="create_lab"),
    path("step-1/", views.step1, name="step1"),
    path("step-2/<int:draft_id>/", views.step2, name="step2"),
    path("step-3/<int:draft_id>/", views.step3, name="step3"),
    path("step-4/<int:draft_id>/", views.step4, name="step4"),

    # Post-apply landing page
    path("success/<int:lab_id>/", views.success, name="success"),
]
