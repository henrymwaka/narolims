# lims_core/wizard/urls.py

from django.urls import path
from . import views

app_name = "wizard"

urlpatterns = [
    # /lims/wizard/  -> step 1
    path("", views.step1, name="step1"),

    # /lims/wizard/step-1/
    path("step-1/", views.step1, name="step1"),

    # /lims/wizard/step-2/<draft_id>/
    path("step-2/<int:draft_id>/", views.step2, name="step2"),
]
