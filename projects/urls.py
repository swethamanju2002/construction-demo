from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # Site Administrator Routes
    path('admin-portal/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-portal/site/create/', views.admin_site_create, name='admin_site_create'),
    path('admin-portal/site/<int:site_id>/', views.admin_site_detail, name='admin_site_detail'),
    path('admin-portal/site/<int:site_id>/edit/', views.admin_site_edit, name='admin_site_edit'),
    
    # Dynamic APIs (AJAX & Form Fallback)
    path('admin-portal/api/toggle-task/', views.api_toggle_task, name='api_toggle_task'),
    path('admin-portal/api/toggle-category/', views.api_toggle_category, name='api_toggle_category'),
    path('admin-portal/api/update-category-percentage/', views.api_update_category_percentage, name='api_update_category_percentage'),

    # Client / Homeowner Routes
    path('client-portal/dashboard/', views.client_dashboard, name='client_dashboard'),
    path('client-portal/site/<int:site_id>/', views.client_site_detail, name='client_site_detail'),

    # Client Management Routes (Admin)
    path('admin-portal/clients/', views.admin_client_list, name='admin_client_list'),
    path('admin-portal/clients/create/', views.admin_client_create, name='admin_client_create'),
    path('admin-portal/api/create-client/', views.api_create_client, name='api_create_client'),
]
