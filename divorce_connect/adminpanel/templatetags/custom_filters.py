from django import template

register = template.Library()


@register.filter
def endswith(value, suffix):
    """
    Returns True if the value ends with the suffix.
    Usage: {{ filename|endswith:".pdf" }}
    """
    if value is None:
        return False
    return str(value).endswith(suffix)
