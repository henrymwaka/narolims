# lims_core/templatetags/dict_extras.py

from __future__ import annotations

import json
from typing import Any

from django import template

register = template.Library()


def _is_dict_like(value: Any) -> bool:
    return hasattr(value, "get") and callable(getattr(value, "get", None))


@register.filter(name="get_item")
def get_item(value: Any, key: Any):
    """
    Safe dictionary accessor for Django templates.

    Usage:
        {{ mydict|get_item:some_key }}
        {{ mydict|get_item:'literal_key' }}

    Works with dict-like objects. Returns None if missing.
    """
    if value is None:
        return None

    if isinstance(value, dict):
        return value.get(key)

    if _is_dict_like(value):
        try:
            return value.get(key)
        except Exception:
            return None

    try:
        return value[key]
    except Exception:
        return None


@register.filter(name="get_item_default")
def get_item_default(value: Any, arg: Any):
    """
    Safe dict accessor with default.

    Usage:
        {{ mydict|get_item_default:'key|Fallback' }}
        {{ mydict|get_item_default:some_var_with_pipe }}

    If the key exists but value is falsy (e.g. ''), it will still return it.
    Only returns default when key is missing or lookup fails.
    """
    if arg is None:
        return get_item(value, arg)

    try:
        s = str(arg)
    except Exception:
        s = ""

    if "|" not in s:
        return get_item(value, s)

    key, default = s.split("|", 1)

    if value is None:
        return default

    # dict
    if isinstance(value, dict):
        if key in value:
            return value.get(key)
        return default

    # dict-like
    if _is_dict_like(value):
        try:
            marker = object()
            got = value.get(key, marker)
            return default if got is marker else got
        except Exception:
            return default

    # __getitem__
    try:
        return value[key]
    except Exception:
        return default


@register.filter(name="has_key")
def has_key(value: Any, key: Any) -> bool:
    """
    Check presence of key in a dict/dict-like.

    Usage:
        {% if mydict|has_key:'lab_id' %}...{% endif %}
    """
    if value is None:
        return False

    if isinstance(value, dict):
        return key in value

    if _is_dict_like(value):
        try:
            marker = object()
            return value.get(key, marker) is not marker
        except Exception:
            return False

    try:
        value[key]  # noqa: B018
        return True
    except Exception:
        return False


@register.filter(name="to_int")
def to_int(value: Any, default: int = 0) -> int:
    """
    Best-effort int conversion for templates.

    Usage:
        {{ x|to_int }}
    """
    try:
        if value is None or value == "":
            return int(default)
        return int(value)
    except Exception:
        try:
            return int(default)
        except Exception:
            return 0


@register.filter(name="to_str")
def to_str(value: Any) -> str:
    """
    Best-effort string conversion.
    """
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


@register.filter(name="json_pretty")
def json_pretty(value: Any) -> str:
    """
    Pretty-print JSON for debug views.

    Usage:
        <pre>{{ payload|json_pretty }}</pre>
    """
    if value is None:
        return ""

    try:
        return json.dumps(value, indent=2, sort_keys=True, default=str)
    except Exception:
        try:
            return str(value)
        except Exception:
            return ""
