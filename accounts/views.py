from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import StyledAuthenticationForm


def login_view(request):
    """
    Role-aware authentication portal.
    """
    if request.user.is_authenticated:
        return redirect('accounts:login_redirect')

    if request.method == 'POST':
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('accounts:login_redirect')
        else:
            messages.error(request, "Invalid username or password. Please verify credentials.")
    else:
        form = StyledAuthenticationForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """
    Terminates session and returns to public homepage.
    """
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('core:home')


def login_redirect(request):
    """
    Directs authenticated user based on role:
    - Site Admin -> Admin Dashboard
    - Client -> Client Dashboard
    """
    user = request.user
    if not user.is_authenticated:
        return redirect('accounts:login')

    if user.is_superuser or user.is_site_admin:
        return redirect('projects:admin_dashboard')
    elif user.is_client:
        return redirect('projects:client_dashboard')
    return redirect('core:home')

