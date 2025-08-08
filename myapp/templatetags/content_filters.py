from django import template

register = template.Library()

@register.filter
def content_type_icon(content_type):
    # Your logic to determine the icon based on content type
    if content_type == 'video':
        return 'fa-video'
    elif content_type == 'article':
        return 'fa-file-text'
    elif content_type == 'image':
        return 'fa-image'
    else:
        return 'fa-file'