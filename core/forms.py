from django import forms
from .models import ContactInquiry


class ContactInquiryForm(forms.ModelForm):
    class Meta:
        model = ContactInquiry
        fields = ['name', 'email', 'phone', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Full Name',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'name@domain.com',
                'required': True,
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 000-0000',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. New Residential Construction Inquiry',
                'required': True,
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tell us about your project specifications, site location, and estimated timeline...',
                'required': True,
            }),
        }
