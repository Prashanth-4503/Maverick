from django import template

register = template.Library()




@register.filter(name='get_item')
def get_item(dictionary, key, default=''):
    """Get a value from a dictionary by key with optional default"""
    return dictionary.get(key, default)

@register.filter(name='split')
def split(value, delimiter=','):
    """
    Split a string by the given delimiter and clean the results
    Returns a list of non-empty, stripped strings
    """
    if not value:
        return []
    return [item.strip() for item in str(value).split(delimiter) if item.strip()]

@register.filter(name='to_list')
def to_list(value):
    """Convert a string to list if it isn't already one"""
    if isinstance(value, list):
        return value
    return [value] if value else []





@register.filter
def abs(value):
    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return value