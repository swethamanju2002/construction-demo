from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('redirect/', views.login_redirect, name='login_redirect'),
    path(
        'password-setup/complete/',
        TemplateView.as_view(
            template_name='accounts/client_password_setup_complete.html'
        ),
        name='client_password_setup_complete',
    ),
    path(
        'password-setup/<uidb64>/<token>/',
        views.ClientPasswordSetupView.as_view(),
        name='client_password_setup',
    ),
]
