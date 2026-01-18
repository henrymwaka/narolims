# lims_core/views_ui_entry.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from lims_core.models import UserRole
from lims_core.models.core import Project


@login_required
def ui_entry(request):
    """
    Stabilizer for Track A:
    - If the user has labs but no projects in scope, route them into the wizard.
    - Otherwise, send them to the real workspace page.
    """
    lab_ids = list(
        UserRole.objects.filter(user=request.user).values_list("laboratory_id", flat=True)
    )

    if lab_ids:
        has_projects = Project.objects.filter(laboratory_id__in=lab_ids).exists()
        if not has_projects:
            return redirect("lims_core:wizard:step1")

    return redirect("lims_core:ui-workspace")
