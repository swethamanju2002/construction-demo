from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username or email',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        })
    )


class ClientSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('new_password1', 'new_password2'):
            self.fields[field_name].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'new-password',
            })


class ClientCreationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Set secure initial password',
        }),
        help_text=(
            "Set an initial password. Use the client directory’s Send portal access "
            "button to email the username and a secure password setup link."
        )
    )

    class Meta:
        from .models import User
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'company_name', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. michael_scott'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Michael'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Scott'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'client@domain.com'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 000-0000'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional company / entity'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_client = True
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

