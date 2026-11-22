from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class WorkCategory(models.Model):
    """
    Master Work Categories. Mandatory (Building, Electrical, Plumbing)
    and Optional (Showcase, Wall Ceiling).
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_mandatory = models.BooleanField(
        default=False,
        help_text="Mandatory categories are enabled by default on all sites."
    )
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Work Category"
        verbose_name_plural = "Work Categories"

    def __str__(self):
        status = "Mandatory" if self.is_mandatory else "Optional"
        return f"{self.name} ({status})"


class ConstructionSite(models.Model):
    """
    Represents a construction project assigned to a client.
    """
    STATUS_PLANNING = 'PLANNING'
    STATUS_ONGOING = 'ONGOING'
    STATUS_ON_HOLD = 'ON_HOLD'
    STATUS_COMPLETED = 'COMPLETED'

    STATUS_CHOICES = [
        (STATUS_PLANNING, 'Planning'),
        (STATUS_ONGOING, 'Ongoing'),
        (STATUS_ON_HOLD, 'On Hold'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    name = models.CharField(max_length=200, help_text="e.g. Skyline Villa Residence")
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_sites',
        help_text="The homeowner/client authorized to view this project."
    )
    site_address = models.TextField()
    start_date = models.DateField(default=timezone.now)
    estimated_completion_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ONGOING
    )
    project_manager = models.CharField(
        max_length=150,
        default="Eng. Robert Vance (Senior Project Lead)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Construction Site"
        verbose_name_plural = "Construction Sites"

    def __str__(self):
        return f"{self.name} - {self.client.get_full_name() or self.client.username}"

    def calculate_overall_progress(self) -> Decimal:
        """
        Calculates overall project progress across all currently ENABLED categories:
        Overall Progress = sum(Progress % of Enabled Categories) / count(Enabled Categories)
        Disabled optional categories are excluded from both numerator and denominator.
        """
        enabled_categories = self.category_progresses.filter(is_enabled=True)
        count = enabled_categories.count()
        if count == 0:
            return Decimal('0.00')

        total_sum = sum(
            Decimal(str(cat.progress_percentage))
            for cat in enabled_categories
        )
        overall = total_sum / Decimal(str(count))
        # Clamp strictly between 0.00 and 100.00 and round to 2 decimal places
        clamped = max(Decimal('0.00'), min(Decimal('100.00'), overall))
        return round(clamped, 2)

    @property
    def overall_progress_percentage(self) -> float:
        """Helper for template/JSON serializing as float."""
        return float(self.calculate_overall_progress())

    @property
    def remaining_percentage(self) -> float:
        return round(100.0 - self.overall_progress_percentage, 2)

    @property
    def status_badge_class(self) -> str:
        mapping = {
            self.STATUS_PLANNING: 'badge-planning',
            self.STATUS_ONGOING: 'badge-ongoing',
            self.STATUS_ON_HOLD: 'badge-hold',
            self.STATUS_COMPLETED: 'badge-completed',
        }
        return mapping.get(self.status, 'badge-secondary')


class SiteCategoryProgress(models.Model):
    """
    Site-specific progress tracking for a given WorkCategory.
    """
    site = models.ForeignKey(
        ConstructionSite,
        on_delete=models.CASCADE,
        related_name='category_progresses'
    )
    category = models.ForeignKey(
        WorkCategory,
        on_delete=models.CASCADE,
        related_name='site_progresses'
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Mandatory categories are enabled by default; optional categories can be toggled by Admin."
    )
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Completion percentage (0% to 100%)."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__order', 'category__id']
        constraints = [
            models.UniqueConstraint(fields=['site', 'category'], name='unique_site_category')
        ]
        verbose_name = "Site Category Progress"
        verbose_name_plural = "Site Category Progresses"

    def __str__(self):
        state = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.site.name} - {self.category.name}: {self.progress_percentage}% ({state})"

    def recalculate_from_tasks(self) -> Decimal:
        """
        Recalculates progress_percentage based on completed SiteTasks.
        """
        total = self.tasks.count()
        if total == 0:
            return self.progress_percentage

        completed = self.tasks.filter(is_completed=True).count()
        calc = (Decimal(completed) / Decimal(total)) * Decimal('100.00')
        self.progress_percentage = round(calc, 2)
        self.save(update_fields=['progress_percentage', 'updated_at'])
        return self.progress_percentage

    @property
    def completed_tasks_count(self) -> int:
        return self.tasks.filter(is_completed=True).count()

    @property
    def total_tasks_count(self) -> int:
        return self.tasks.count()


class SiteTask(models.Model):
    """
    Subtask checklist item within a SiteCategoryProgress.
    """
    site_category = models.ForeignKey(
        SiteCategoryProgress,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    task_name = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Site Task"
        verbose_name_plural = "Site Tasks"

    def __str__(self):
        status = "✓ Done" if self.is_completed else "○ Pending"
        return f"[{status}] {self.task_name} ({self.site_category.category.name})"

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completed_date:
            self.completed_date = timezone.now()
        elif not self.is_completed:
            self.completed_date = None
        super().save(*args, **kwargs)


class ProjectUpdateImage(models.Model):
    """
    Verified progress photos uploaded by the Site Administrator.
    """
    site = models.ForeignKey(
        ConstructionSite,
        on_delete=models.CASCADE,
        related_name='update_images'
    )
    category = models.ForeignKey(
        WorkCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='update_images',
        help_text="Optional category tag"
    )
    image = models.ImageField(upload_to='site_updates/%Y/%m/')
    caption = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Project Update Image"
        verbose_name_plural = "Project Update Images"

    def __str__(self):
        return f"{self.site.name} - {self.caption} ({self.uploaded_at.strftime('%Y-%m-%d')})"


class SiteProgressHistory(models.Model):
    """
    Audit log of site progress milestones.
    """
    site = models.ForeignKey(
        ConstructionSite,
        on_delete=models.CASCADE,
        related_name='progress_history'
    )
    overall_progress = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = "Site Progress History"
        verbose_name_plural = "Site Progress Histories"

    def __str__(self):
        return f"{self.site.name} at {self.overall_progress}% on {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"


class Notification(models.Model):
    KIND_TASK_PROGRESS = 'task_progress'
    KIND_PROJECT_UPDATE = 'project_update'
    KIND_SITE_STATUS = 'site_status'
    KIND_SCHEDULE_CHANGE = 'schedule_change'
    KIND_DUE_DATE = 'due_date'
    KIND_SITE_ALERT = 'site_alert'
    KIND_CONTACT_INQUIRY = 'contact_inquiry'

    KIND_CHOICES = [
        (KIND_TASK_PROGRESS, 'Task and progress update'),
        (KIND_PROJECT_UPDATE, 'Project update'),
        (KIND_SITE_STATUS, 'Project status'),
        (KIND_SCHEDULE_CHANGE, 'Schedule change'),
        (KIND_DUE_DATE, 'Due date reminder'),
        (KIND_SITE_ALERT, 'Site alert or milestone'),
        (KIND_CONTACT_INQUIRY, 'Contact inquiry'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    site = models.ForeignKey(
        ConstructionSite,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    title = models.CharField(max_length=180)
    message = models.TextField()
    url = models.CharField(max_length=500, blank=True)
    event_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'event_key'],
                name='unique_recipient_notification_event',
            ),
        ]
        indexes = [
            models.Index(fields=['recipient', 'read_at', '-created_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.recipient.username})"

