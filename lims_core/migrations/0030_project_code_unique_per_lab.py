# lims_core/migrations/0030_project_code_unique_per_lab.py

from django.db import migrations, models
from django.db.models import Count


def dedupe_project_codes_per_lab(apps, schema_editor):
    """
    Merge duplicate Projects that share the same (laboratory_id, code).

    Strategy:
    - For each duplicate group, keep the lowest Project.id as canonical.
    - Repoint all FK references from dropped projects to the kept project.
    - Delete the dropped projects.
    """
    Project = apps.get_model("lims_core", "Project")

    # Find duplicate groups
    dups = (
        Project.objects.values("laboratory_id", "code")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .order_by("-n", "laboratory_id", "code")
    )

    if not dups.exists():
        return

    # Find all FK fields pointing to Project across the migration app registry
    fk_links = []
    for M in apps.get_models():
        for f in M._meta.fields:
            remote = getattr(f, "remote_field", None)
            if remote and getattr(remote, "model", None) == Project:
                fk_links.append((M, f))

    for row in dups:
        lab_id = row["laboratory_id"]
        code = row["code"]

        ids = list(
            Project.objects.filter(laboratory_id=lab_id, code=code)
            .order_by("id")
            .values_list("id", flat=True)
        )
        if len(ids) < 2:
            continue

        keep_id = ids[0]
        drop_ids = ids[1:]

        for drop_id in drop_ids:
            # Repoint every FK(project_id) from drop -> keep
            for M, f in fk_links:
                att = f.attname  # usually "<fieldname>_id"
                M.objects.filter(**{att: drop_id}).update(**{att: keep_id})

            # Now it is safe to delete the duplicate project
            Project.objects.filter(id=drop_id).delete()


class Migration(migrations.Migration):
    # Critical: allow DML and DDL to occur in separate transactions.
    atomic = False

    dependencies = [
        ("lims_core", "0029_labconfigdraft"),
    ]

    operations = [
        migrations.RunPython(dedupe_project_codes_per_lab, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.UniqueConstraint(
                fields=["laboratory", "code"],
                name="uniq_project_code_per_lab",
            ),
        ),
    ]
