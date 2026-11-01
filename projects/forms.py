from django import forms
from accounts.models import User
from .models import ConstructionSite, ProjectUpdateImage, SiteCategoryProgress, SiteTask


class ConstructionSiteForm(forms.ModelForm):
    class Meta:
        model = ConstructionSite
        fields = [
            'name',
            'client',
            'site_address',
            'start_date',
            'estimated_completion_date',
            'status',
            'project_manager',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Skyline Villa Residence'
            }),
            'client': forms.Select(attrs={
                'class': 'form-select'
            }),
            'site_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full physical plot/street address'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'estimated_completion_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'project_manager': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lead Architect / Engineer Name'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prioritize clients in dropdown
        self.fields['client'].queryset = User.objects.filter(is_client=True)
        if not self.fields['client'].queryset.exists():
            # Fallback to any user if no client registered yet
            self.fields['client'].queryset = User.objects.all()


class ProjectUpdateImageForm(forms.ModelForm):
    class Meta:
        model = ProjectUpdateImage
        fields = ['image', 'caption', 'category']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Concrete curing on 2nd floor slab'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
