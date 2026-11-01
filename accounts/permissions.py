from functools import wraps
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def site_admin_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a site administrator.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please log in with administrator credentials.")
            return redirect('accounts:login')
        if not (request.user.is_site_admin or request.user.is_superuser):
            raise PermissionDenied("Access restricted to Site Administrators.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def client_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is an authorized client.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please log in to access your client portal.")
            return redirect('accounts:login')
        if not (request.user.is_client or request.user.is_superuser):
            raise PermissionDenied("Access restricted to authorized clients.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class SiteAdminRequiredMixin(UserPassesTestMixin):
    """
    CBV mixin that enforces Site Administrator permissions.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_site_admin or user.is_superuser)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('accounts:login')
        raise PermissionDenied("Access restricted to Site Administrators.")


class ClientRequiredMixin(UserPassesTestMixin):
    """
    CBV mixin that enforces Client role permissions.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_client or user.is_superuser)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('accounts:login')
        raise PermissionDenied("Access restricted to authorized clients.")
