from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a dynamic key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def get_field(form, field_name):
    """Get a form field by name"""
    return form[f'score_{field_name}']
