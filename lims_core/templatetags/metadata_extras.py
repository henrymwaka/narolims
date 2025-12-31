# lims_core/templatetags/metadata_extras.py

from __future__ import annotations

from collections.abc import Mapping
from django import template

register = template.Library()


@register.filter(name="get_item")
def get_item(obj, key):
    """
    Safe dict lookup for Django templates.

    - If obj is None, returns None
    - If obj is a Mapping, returns obj.get(key)
    - Otherwise returns None
    """
    if obj is None:
        return None

    if isinstance(obj, Mapping):
        return obj.get(key)

    return None
