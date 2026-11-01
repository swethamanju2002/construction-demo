from django.db import models


class ContactInquiry(models.Model):
    """
    Inquiries submitted from the public contact form.
    """
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_addressed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contact Inquiry"
        verbose_name_plural = "Contact Inquiries"

    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%Y-%m-%d')})"

