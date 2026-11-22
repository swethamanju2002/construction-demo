from uuid import uuid4

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import ConstructionSite, Notification


def create_notification(*, recipient, kind, title, message, url='', site=None, event_key=None):
    key = event_key or uuid4().hex
    notification, _ = Notification.objects.get_or_create(
        recipient=recipient,
        event_key=key,
        defaults={
            'kind': kind,
            'title': title,
            'message': message,
            'url': url,
            'site': site,
        },
    )
    return notification


def notify_site_client(*, site, kind, title, message, event_key=None):
    return create_notification(
        recipient=site.client,
        site=site,
        kind=kind,
        title=title,
        message=message,
        url=reverse('projects:client_site_detail', args=[site.id]),
        event_key=event_key,
    )


def notify_site_admins(*, kind, title, message, site=None, url='', event_key=None):
    key = event_key or uuid4().hex
    admins = User.objects.filter(is_active=True).filter(
        Q(is_site_admin=True) | Q(is_superuser=True)
    ).distinct()
    return [
        create_notification(
            recipient=admin,
            site=site,
            kind=kind,
            title=title,
            message=message,
            url=url or (
                reverse('projects:admin_site_detail', args=[site.id]) if site else ''
            ),
            event_key=key,
        )
        for admin in admins
    ]


def sync_scheduled_notifications(user):
    today = timezone.localdate()
    if user.is_superuser or user.is_site_admin:
        on_hold_sites = ConstructionSite.objects.filter(
            status=ConstructionSite.STATUS_ON_HOLD
        ).select_related('client')
        for site in on_hold_sites:
            notify_site_admins(
                kind=Notification.KIND_SITE_ALERT,
                title='Site on hold',
                message=f'{site.name} is currently on hold.',
                site=site,
                event_key=f'site:{site.id}:on-hold:current',
            )

        overdue_sites = ConstructionSite.objects.filter(
            status=ConstructionSite.STATUS_ONGOING,
            estimated_completion_date__lt=today,
        ).prefetch_related('category_progresses')
        for site in overdue_sites:
            if site.calculate_overall_progress() < 100:
                notify_site_admins(
                    kind=Notification.KIND_SITE_ALERT,
                    title='Project past estimated completion',
                    message=(
                        f'{site.name} is still marked ongoing after its estimated '
                        f'completion date of {site.estimated_completion_date:%b %d, %Y}.'
                    ),
                    site=site,
                    event_key=(
                        f'site:{site.id}:overdue:'
                        f'{site.estimated_completion_date.isoformat()}'
                    ),
                )
        return

    if not user.is_client:
        return

    sites = user.assigned_sites.exclude(
        status=ConstructionSite.STATUS_COMPLETED
    ).select_related('client')
    for site in sites:
        days_until_due = (site.estimated_completion_date - today).days
        if days_until_due < 0:
            notify_site_client(
                site=site,
                kind=Notification.KIND_DUE_DATE,
                title='Estimated completion date passed',
                message=(
                    f'The estimated completion date for {site.name} '
                    f'({site.estimated_completion_date:%b %d, %Y}) has passed.'
                ),
                event_key=(
                    f'site:{site.id}:client-overdue:'
                    f'{site.estimated_completion_date.isoformat()}'
                ),
            )
        elif days_until_due <= 7:
            due_message = (
                f'{site.name} is estimated to complete today.'
                if days_until_due == 0
                else (
                    f'{site.name} is estimated to complete tomorrow.'
                    if days_until_due == 1
                    else f'{site.name} is estimated to complete in {days_until_due} days.'
                )
            )
            notify_site_client(
                site=site,
                kind=Notification.KIND_DUE_DATE,
                title='Estimated completion is approaching',
                message=due_message,
                event_key=(
                    f'site:{site.id}:client-upcoming:'
                    f'{site.estimated_completion_date.isoformat()}'
                ),
            )
