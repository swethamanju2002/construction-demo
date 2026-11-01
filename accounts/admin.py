from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('CRM Roles & Contact', {
            'fields': ('is_site_admin', 'is_client', 'phone_number', 'company_name')
        }),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_site_admin', 'is_client', 'is_staff')
    list_filter = ('is_site_admin', 'is_client', 'is_staff', 'is_superuser')

