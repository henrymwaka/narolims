from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    try:
        return d.get(int(key)) if isinstance(d, dict) else None
    except Exception:
        try:
            return d.get(key) if isinstance(d, dict) else None
        except Exception:
            return None
