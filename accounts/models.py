from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model supporting Site Administrators and Client/Homeowner roles.
    """
    is_site_admin = models.BooleanField(
        default=False,
        help_text="Designates whether the user is a construction site administrator."
    )
    is_client = models.BooleanField(
        default=False,
        help_text="Designates whether the user is a client / homeowner."
    )
    phone_number = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    @property
    def role_label(self):
        if self.is_superuser or self.is_site_admin:
            return "Site Administrator"
        if self.is_client:
            return "Client / Homeowner"
        return "Standard User"

    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            return f"{full_name} ({self.username}) - {self.role_label}"
        return f"{self.username} ({self.role_label})"

