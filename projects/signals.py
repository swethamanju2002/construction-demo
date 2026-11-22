from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from .models import (
    ConstructionSite,
    Notification,
    ProjectUpdateImage,
    SiteCategoryProgress,
    SiteTask,
    WorkCategory,
)
from .notifications import notify_site_admins, notify_site_client

# Standard blueprint categories and subtask checklists
STANDARD_CATEGORIES = [
    {
        'name': 'Building Work',
        'slug': 'building-work',
        'is_mandatory': True,
        'order': 1,
        'description': 'Structural foundations, masonry, concrete casting, and external finishing.',
        'tasks': [
            'Basement',
            'Lintel',
            'Roof Concrete',
            'Finishing Touch',
        ],
    },
    {
        'name': 'Electrical Work',
        'slug': 'electrical-work',
        'is_mandatory': True,
        'order': 2,
        'description': 'Concealed conduit piping, power distribution wiring, and switchboard fixtures.',
        'tasks': [
            'Wiring Pipe Concealing',
            'Wiring',
            'Switchboard Fixing and Light Fitting',
        ],
    },
    {
        'name': 'Plumbing Work',
        'slug': 'plumbing-work',
        'is_mandatory': True,
        'order': 3,
        'description': 'Concealed water pipelines, supply/drainage fitting, rooftop water storage, and sanitary fixtures.',
        'tasks': [
            'Water Line Pipe Concealing',
            'Water Input & Output Pipe Fitting',
            'Water Tank Fixing',
            'Bathroom Fittings Fixing',
        ],
    },
    {
        'name': 'Showcase Work',
        'slug': 'showcase-work',
        'is_mandatory': False,
        'order': 4,
        'description': 'Custom architectural cabinetry, modular millwork, and decorative display showcases.',
        'tasks': [
            'Planning',
            'Base Fitting',
            'Completing',
        ],
    },
    {
        'name': 'Wall Ceiling Work',
        'slug': 'wall-ceiling-work',
        'is_mandatory': False,
        'order': 5,
        'description': 'False ceiling grid planning, perimeter channel installation, and acoustic gypsum completion.',
        'tasks': [
            'Planning',
            'Channel Fitting',
            'Completing',
        ],
    },
]


def ensure_master_categories():
    """
    Ensures that the 5 standard categories exist in the database.
    Returns a dict mapping category slug to WorkCategory instance.
    """
    category_map = {}
    for cat_data in STANDARD_CATEGORIES:
        category, _ = WorkCategory.objects.get_or_create(
            slug=cat_data['slug'],
            defaults={
                'name': cat_data['name'],
                'is_mandatory': cat_data['is_mandatory'],
                'order': cat_data['order'],
                'description': cat_data['description'],
            }
        )
        category_map[cat_data['slug']] = (category, cat_data['tasks'])
    return category_map


@receiver(post_save, sender=ConstructionSite)
def auto_populate_site_categories_and_tasks(sender, instance, created, **kwargs):
    """
    On site creation:
    1. Ensures master categories exist.
    2. Initializes SiteCategoryProgress for all 5 categories:
       - 3 Mandatory categories enabled by default
       - 2 Optional categories disabled by default
    3. Auto-populates predefined SiteTasks for each category.
    """
    if not created:
        return

    category_map = ensure_master_categories()

    for cat_data in STANDARD_CATEGORIES:
        category, tasks = category_map[cat_data['slug']]
        site_progress, _ = SiteCategoryProgress.objects.get_or_create(
            site=instance,
            category=category,
            defaults={
                'is_enabled': category.is_mandatory,
                'progress_percentage': 0.00,
            }
        )

        # Populate tasks for this category
        for idx, task_name in enumerate(tasks, start=1):
            SiteTask.objects.get_or_create(
                site_category=site_progress,
                task_name=task_name,
                defaults={
                    'is_completed': False,
                    'order': idx,
                }
            )


@receiver(post_save, sender=SiteTask)
def update_category_progress_on_task_change(sender, instance, **kwargs):
    """
    Automatically recalculate the parent category's progress percentage
    whenever a subtask is updated or completed.
    """
    if kwargs.get('update_fields') and 'progress_percentage' in kwargs['update_fields']:
        return
    instance.site_category.recalculate_from_tasks()


@receiver(pre_save, sender=ConstructionSite)
def capture_site_notification_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._notification_previous_state = None
        return
    instance._notification_previous_state = sender.objects.filter(
        pk=instance.pk
    ).values('client_id', 'status', 'estimated_completion_date').first()


@receiver(post_save, sender=ConstructionSite)
def notify_site_assignment_and_changes(sender, instance, created, **kwargs):
    previous = getattr(instance, '_notification_previous_state', None)
    if created:
        notify_site_client(
            site=instance,
            kind=Notification.KIND_PROJECT_UPDATE,
            title='A construction project was added to your portal',
            message=f'{instance.name} is now available in your client project portal.',
            event_key=f'site:{instance.id}:assigned:{instance.client_id}',
        )
        return
    if not previous:
        return

    update_fields = kwargs.get('update_fields')
    if (
        previous['client_id'] != instance.client_id
        and (not update_fields or 'client' in update_fields or 'client_id' in update_fields)
    ):
        notify_site_client(
            site=instance,
            kind=Notification.KIND_PROJECT_UPDATE,
            title='A project was assigned to your portal',
            message=f'{instance.name} is now available in your client project portal.',
            event_key=f'site:{instance.id}:assigned:{instance.client_id}',
        )

    if (
        previous['status'] != instance.status
        and (not update_fields or 'status' in update_fields)
    ):
        notify_site_client(
            site=instance,
            kind=Notification.KIND_SITE_STATUS,
            title='Project status updated',
            message=f'{instance.name} is now {instance.get_status_display()}.',
            feedback_requested=True,
        )
        if instance.status in (
            ConstructionSite.STATUS_ON_HOLD,
            ConstructionSite.STATUS_COMPLETED,
        ):
            notify_site_admins(
                kind=Notification.KIND_SITE_ALERT,
                title=(
                    'Project completed'
                    if instance.status == ConstructionSite.STATUS_COMPLETED
                    else 'Site placed on hold'
                ),
                message=f'{instance.name} is now {instance.get_status_display()}.',
                site=instance,
                event_key=f'site:{instance.id}:on-hold:current',
            )

    if (
        previous['estimated_completion_date'] != instance.estimated_completion_date
        and (
            not update_fields
            or 'estimated_completion_date' in update_fields
        )
    ):
        notify_site_client(
            site=instance,
            kind=Notification.KIND_SCHEDULE_CHANGE,
            title='Estimated completion date changed',
            message=(
                f'The estimated completion date for {instance.name} is now '
                f'{instance.estimated_completion_date:%b %d, %Y}.'
            ),
            feedback_requested=True,
        )


@receiver(pre_save, sender=SiteCategoryProgress)
def capture_category_notification_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._notification_previous_state = None
        return
    instance._notification_previous_state = sender.objects.filter(
        pk=instance.pk
    ).values('progress_percentage', 'is_enabled').first()


@receiver(post_save, sender=SiteCategoryProgress)
def notify_category_progress_changes(sender, instance, created, **kwargs):
    previous = getattr(instance, '_notification_previous_state', None)
    if created or not previous:
        return

    site = instance.site
    category_name = instance.category.name
    update_fields = kwargs.get('update_fields')
    old_progress = previous['progress_percentage']
    if (
        old_progress != instance.progress_percentage
        and (not update_fields or 'progress_percentage' in update_fields)
    ):
        notify_site_client(
            site=site,
            kind=Notification.KIND_TASK_PROGRESS,
            title=f'{category_name} progress updated',
            message=(
                f'{category_name} is now {instance.progress_percentage}% complete '
                f'({instance.completed_tasks_count} of {instance.total_tasks_count} tasks).'
            ),
            feedback_requested=True,
        )
        if old_progress < 100 <= instance.progress_percentage:
            notify_site_admins(
                kind=Notification.KIND_SITE_ALERT,
                title='Work category milestone reached',
                message=f'{site.name}: {category_name} is 100% complete.',
                site=site,
            )

    if (
        previous['is_enabled'] != instance.is_enabled
        and (not update_fields or 'is_enabled' in update_fields)
    ):
        state = 'enabled' if instance.is_enabled else 'disabled'
        notify_site_client(
            site=site,
            kind=Notification.KIND_TASK_PROGRESS,
            title=f'{category_name} {state}',
            message=(
                f'{category_name} was {state}. Project progress is calculated '
                'using enabled work categories.'
            ),
            feedback_requested=True,
        )


@receiver(post_save, sender=ProjectUpdateImage)
def notify_client_of_project_photo(sender, instance, created, **kwargs):
    if not created:
        return
    category_name = instance.category.name if instance.category else 'General site'
    notify_site_client(
        site=instance.site,
        kind=Notification.KIND_PROJECT_UPDATE,
        title='New site photo update',
        message=f'{category_name}: {instance.caption}',
        feedback_requested=True,
    )


@receiver(post_save, sender='core.ContactInquiry')
def notify_admins_of_contact_inquiry(sender, instance, created, **kwargs):
    if not created:
        return
    notify_site_admins(
        kind=Notification.KIND_CONTACT_INQUIRY,
        title='New project inquiry',
        message=f'{instance.name}: {instance.subject}',
        url=f'{reverse("projects:admin_inquiries")}#inquiry-{instance.id}',
    )
