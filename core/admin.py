from django.contrib import admin
from .models import ContactInquiry


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'subject', 'created_at', 'is_addressed')
    list_filter = ('is_addressed', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')

