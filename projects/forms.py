from django import forms
from accounts.models import User
from .models import (
    ClientFeedback,
    ConstructionSite,
    ProjectUpdateImage,
    SiteMaterial,
    SiteCategoryProgress,
    SiteTask,
)


class ConstructionSiteForm(forms.ModelForm):
    showcase_work = forms.BooleanField(
        required=False,
        initial=False,
        label='Showcase Work',
    )
    wall_ceiling_work = forms.BooleanField(
        required=False,
        initial=False,
        label='Wall Ceiling Work',
    )

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
        if self.instance and self.instance.pk:
            category_states = dict(
                self.instance.category_progresses.values_list(
                    'category__slug',
                    'is_enabled',
                )
            )
            self.fields['showcase_work'].initial = category_states.get('showcase-work', False)
            self.fields['wall_ceiling_work'].initial = category_states.get('wall-ceiling-work', False)

    def save(self, commit=True):
        site = super().save(commit=commit)
        if not commit:
            return site

        optional_states = {
            'showcase-work': self.cleaned_data['showcase_work'],
            'wall-ceiling-work': self.cleaned_data['wall_ceiling_work'],
        }
        for slug, is_enabled in optional_states.items():
            category_progress = site.category_progresses.filter(category__slug=slug).first()
            if category_progress:
                category_progress.is_enabled = is_enabled
                category_progress.save(update_fields=['is_enabled', 'updated_at'])

        # Mandatory categories are never left disabled.
        site.category_progresses.filter(
            category__is_mandatory=True
        ).exclude(is_enabled=True).update(is_enabled=True)
        return site


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


class SiteMaterialForm(forms.ModelForm):
    class Meta:
        model = SiteMaterial
        fields = ['name', 'quantity', 'unit', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Portland cement',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01',
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. bags',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional details',
            }),
        }


class ClientFeedbackForm(forms.ModelForm):
    message = forms.CharField(
        min_length=5,
        max_length=4000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Tell us how the latest project update looks to you.',
        }),
    )

    class Meta:
        model = ClientFeedback
        fields = ['site', 'message']
        widgets = {
            'site': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['site'].queryset = ConstructionSite.objects.none()
