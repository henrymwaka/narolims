from django import template

register = template.Library()

@register.filter
def get_item(obj, key):
    if obj is None:
        return ""
    if isinstance(obj, dict):
        return obj.get(key, "")
    try:
        return getattr(obj, str(key))
    except Exception:
        return ""
