from .models import LaboratoryProfile

def get_lab_profile_for_object(obj):
    """
    Given a Sample, Experiment, or Batch,
    return the associated LaboratoryProfile or None.
    """
    lab = getattr(obj, "laboratory", None)
    if not lab:
        return None

    try:
        return LaboratoryProfile.objects.get(laboratory=lab, is_active=True)
    except LaboratoryProfile.DoesNotExist:
        return None
