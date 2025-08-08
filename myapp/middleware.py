from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages

class ActiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_active:
            messages.warning(request, 'Please verify your email to access this page.')
            return HttpResponseRedirect(reverse('verify_email'))
        return self.get_response(request)