import json
import logging
import smtplib
from decimal import Decimal
from datetime import date
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Avg
from django.http import Http404, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from accounts.models import User
from accounts.forms import ClientCreationForm
from accounts.permissions import site_admin_required, client_required
from core.models import ContactInquiry
from .forms import ClientFeedbackForm, ConstructionSiteForm, ProjectUpdateImageForm
from .models import (
    ClientFeedback,
    ConstructionSite,
    Notification,
    WorkCategory,
    SiteCategoryProgress,
    SiteTask,
    ProjectUpdateImage,
    SiteProgressHistory,
)
from .notifications import notify_site_admins, sync_scheduled_notifications

logger = logging.getLogger(__name__)


def create_client_feedback_notification(feedback):
    notify_site_admins(
        kind=Notification.KIND_CLIENT_FEEDBACK,
        title='New client feedback',
        message=(
            f'{feedback.author.get_full_name() or feedback.author.username} '
            f'shared feedback about {feedback.site.name}.'
        ),
        site=feedback.site,
        url=f'{reverse("projects:admin_feedback")}#feedback-{feedback.id}',
        event_key=f'client-feedback:{feedback.id}',
    )


# ==============================================================================
# SITE ADMINISTRATOR VIEWS
# ==============================================================================

@site_admin_required
def admin_dashboard(request):
    """
    Overview of all construction sites, client assignments, and portfolio metrics.
    """
    sites_qs = ConstructionSite.objects.all().select_related('client').prefetch_related(
        'category_progresses__category'
    )

    # Search & Status filters
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if query:
        sites_qs = sites_qs.filter(name__icontains=query) | sites_qs.filter(client__username__icontains=query) | sites_qs.filter(client__first_name__icontains=query)
    if status_filter:
        sites_qs = sites_qs.filter(status=status_filter)

    sites = list(sites_qs)

    # Dashboard metrics are derived from real records. "Delayed" uses the explicit
    # on-hold status or a past estimated completion date for incomplete ongoing work.
    portfolio_sites = ConstructionSite.objects.all().select_related('client').prefetch_related(
        'category_progresses__category'
    )
    portfolio_list = list(portfolio_sites)
    today = date.today()
    total_sites = len(portfolio_list)
    ongoing_count = sum(
        1 for s in portfolio_list
        if s.status == ConstructionSite.STATUS_ONGOING
    )
    on_track_count = sum(
        1 for s in portfolio_list
        if s.status == ConstructionSite.STATUS_ONGOING
        and s.estimated_completion_date >= today
        and s.calculate_overall_progress() < Decimal('100.00')
    )
    delayed_count = sum(
        1 for s in portfolio_list
        if s.status == ConstructionSite.STATUS_ON_HOLD
        or (
            s.status == ConstructionSite.STATUS_ONGOING
            and s.estimated_completion_date < today
            and s.calculate_overall_progress() < Decimal('100.00')
        )
    )
    completed_count = sum(1 for s in portfolio_list if s.status == ConstructionSite.STATUS_COMPLETED)
    planning_count = sum(1 for s in portfolio_list if s.status == ConstructionSite.STATUS_PLANNING)
    in_progress_count = ongoing_count
    total_clients = User.objects.filter(is_client=True).count()

    # Portfolio average completion
    if total_sites > 0:
        avg_progress = round(sum(s.calculate_overall_progress() for s in sites) / Decimal(total_sites), 2)
    else:
        avg_progress = Decimal('0.00')

    context = {
        'sites': sites,
        'total_sites': total_sites,
        'ongoing_count': ongoing_count,
        'on_track_count': on_track_count,
        'in_progress_count': in_progress_count,
        'delayed_count': delayed_count,
        'completed_count': completed_count,
        'planning_count': planning_count,
        'total_clients': total_clients,
        'avg_progress': avg_progress,
        'query': query,
        'status_filter': status_filter,
        'status_choices': ConstructionSite.STATUS_CHOICES,
    }
    return render(request, 'admin_portal/dashboard.html', context)


@site_admin_required
def admin_site_create(request):
    """
    Create a new construction site. Post-save signal auto-initializes categories and tasks.
    """
    if request.method == 'POST':
        form = ConstructionSiteForm(request.POST)
        if form.is_valid():
            site = form.save()
            messages.success(
                request,
                f"Construction site '{site.name}' created successfully with mandatory categories auto-initialized."
            )
            return redirect('projects:admin_site_detail', site_id=site.id)
    else:
        initial = {}
        client_id = request.GET.get('client')
        if client_id:
            client = User.objects.filter(id=client_id, is_client=True).first()
            if client:
                initial['client'] = client.id
        form = ConstructionSiteForm(initial=initial)

    return render(request, 'admin_portal/site_form.html', {'form': form, 'title': 'Create New Construction Site'})


@site_admin_required
def admin_site_edit(request, site_id):
    """
    Update basic information of a construction site.
    """
    site = get_object_or_404(ConstructionSite, id=site_id)
    if request.method == 'POST':
        form = ConstructionSiteForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, f"Site details for '{site.name}' updated successfully.")
            return redirect('projects:admin_site_detail', site_id=site.id)
    else:
        form = ConstructionSiteForm(instance=site)

    return render(request, 'admin_portal/site_form.html', {
        'form': form,
        'site': site,
        'title': f'Edit Site - {site.name}'
    })


@site_admin_required
def admin_site_detail(request, site_id):
    """
    Detailed administration hub:
    - View/manage all categories
    - Toggle optional categories
    - Checklist task toggle
    - Direct category percentage adjustment
    - Upload verified progress photos
    """
    site = get_object_or_404(
        ConstructionSite.objects.select_related('client').prefetch_related(
            'category_progresses__category',
            'category_progresses__tasks',
            'update_images__category'
        ),
        id=site_id
    )

    # Photo upload form handling
    if request.method == 'POST' and 'upload_photo' in request.POST:
        photo_form = ProjectUpdateImageForm(request.POST, request.FILES)
        if photo_form.is_valid():
            photo = photo_form.save(commit=False)
            photo.site = site
            photo.save()
            messages.success(request, f"New progress photo '{photo.caption}' uploaded successfully.")
            return redirect('projects:admin_site_detail', site_id=site.id)
    else:
        photo_form = ProjectUpdateImageForm()

    # Filter category dropdown for photo form to categories belonging to this site
    photo_form.fields['category'].queryset = WorkCategory.objects.all()

    category_progresses = site.category_progresses.all()
    overall_progress = site.calculate_overall_progress()

    context = {
        'site': site,
        'category_progresses': category_progresses,
        'overall_progress': overall_progress,
        'photo_form': photo_form,
        'photos': site.update_images.all()[:30],
    }
    return render(request, 'admin_portal/site_detail.html', context)


@site_admin_required
def admin_inquiries(request):
    if request.method == 'POST':
        inquiry_id = request.POST.get('inquiry_id')
        inquiry = get_object_or_404(ContactInquiry, pk=inquiry_id)
        inquiry.is_addressed = request.POST.get('is_addressed') == 'true'
        inquiry.save(update_fields=['is_addressed'])
        messages.success(
            request,
            'Inquiry status updated.',
        )
        return redirect(f"{reverse('projects:admin_inquiries')}#inquiry-{inquiry.id}")

    status_filter = request.GET.get('status', 'open')
    inquiries = ContactInquiry.objects.all()
    if status_filter == 'open':
        inquiries = inquiries.filter(is_addressed=False)
    elif status_filter == 'addressed':
        inquiries = inquiries.filter(is_addressed=True)
    else:
        status_filter = 'all'
    return render(request, 'admin_portal/inquiries.html', {
        'inquiries': inquiries,
        'inquiry_status_filter': status_filter,
        'admin_active': 'inquiries',
    })


@site_admin_required
def admin_feedback(request):
    if request.method == 'POST':
        feedback_id = request.POST.get('feedback_id', '')
        if not feedback_id.isdecimal():
            raise Http404
        feedback = get_object_or_404(
            ClientFeedback,
            pk=feedback_id,
        )
        feedback.admin_read_at = (
            timezone.now()
            if request.POST.get('is_read') == 'true'
            else None
        )
        feedback.save(update_fields=['admin_read_at'])
        Notification.objects.filter(
            recipient=request.user,
            event_key=f'client-feedback:{feedback.id}',
        ).update(read_at=feedback.admin_read_at)
        return redirect(f"{reverse('projects:admin_feedback')}#feedback-{feedback.id}")

    status_filter = request.GET.get('status', 'new')
    feedback_entries = ClientFeedback.objects.select_related(
        'author', 'site', 'update_notification'
    )
    if status_filter == 'new':
        feedback_entries = feedback_entries.filter(admin_read_at__isnull=True)
    elif status_filter == 'read':
        feedback_entries = feedback_entries.filter(admin_read_at__isnull=False)
    else:
        status_filter = 'all'
    return render(request, 'admin_portal/feedback.html', {
        'feedback_entries': feedback_entries,
        'feedback_status_filter': status_filter,
        'admin_active': 'feedback',
    })


@client_required
def client_feedback(request):
    assigned_sites = ConstructionSite.objects.filter(client=request.user)
    form = ClientFeedbackForm(
        request.POST if request.method == 'POST' else None
    )
    form.fields['site'].queryset = assigned_sites

    if request.method == 'POST' and form.is_valid():
        feedback = form.save(commit=False)
        feedback.author = request.user
        feedback.save()
        create_client_feedback_notification(feedback)
        messages.success(request, 'Your feedback was sent to the project team.')
        return redirect('projects:client_feedback')

    if request.method == 'GET':
        requested_site_id = request.GET.get('site', '')
        requested_site = (
            assigned_sites.filter(pk=requested_site_id).first()
            if requested_site_id.isdecimal()
            else None
        )
        default_site = requested_site or assigned_sites.first()
        if default_site:
            form.fields['site'].initial = default_site.pk

    return render(request, 'client_portal/feedback.html', {
        'form': form,
        'feedback_entries': ClientFeedback.objects.filter(
            author=request.user
        ).select_related('site', 'update_notification'),
        'has_assigned_sites': assigned_sites.exists(),
        'site': assigned_sites.first(),
        'client_active': 'feedback',
    })


@client_required
@require_GET
def api_pending_client_feedback(request):
    notification = (
        Notification.objects.filter(
            recipient=request.user,
            site__client=request.user,
            feedback_requested=True,
            feedback_prompt_dismissed_at__isnull=True,
            feedback_response__isnull=True,
        )
        .select_related('site')
        .order_by('created_at')
        .first()
    )
    if notification is None:
        return JsonResponse({'request': None})
    return JsonResponse({
        'request': {
            'notification_id': notification.id,
            'site_id': notification.site_id,
            'site_name': notification.site.name,
            'title': notification.title,
            'message': notification.message,
            'created_at': notification.created_at.isoformat(),
        },
    })


@client_required
@require_POST
def api_submit_client_feedback(request):
    notification_id = request.POST.get('notification_id')
    message = request.POST.get('message', '').strip()
    if not notification_id:
        return HttpResponseBadRequest('notification_id is required')
    if not notification_id.isdecimal():
        return HttpResponseBadRequest('notification_id must be an integer')
    if not 5 <= len(message) <= 4000:
        return JsonResponse({
            'success': False,
            'error': 'Feedback must be between 5 and 4000 characters.',
        }, status=400)

    notification = get_object_or_404(
        Notification.objects.filter(
            recipient=request.user,
            site__client=request.user,
            feedback_requested=True,
            feedback_prompt_dismissed_at__isnull=True,
            feedback_response__isnull=True,
        ),
        pk=notification_id,
    )
    feedback, created = ClientFeedback.objects.get_or_create(
        update_notification=notification,
        defaults={
            'author': request.user,
            'site': notification.site,
            'message': message,
        },
    )
    if created:
        create_client_feedback_notification(feedback)
    return JsonResponse({'success': True})


@client_required
@require_POST
def api_dismiss_client_feedback(request):
    notification_id = request.POST.get('notification_id')
    if not notification_id:
        return HttpResponseBadRequest('notification_id is required')
    if not notification_id.isdecimal():
        return HttpResponseBadRequest('notification_id must be an integer')
    notification = get_object_or_404(
        Notification.objects.filter(
            recipient=request.user,
            site__client=request.user,
            feedback_requested=True,
            feedback_prompt_dismissed_at__isnull=True,
            feedback_response__isnull=True,
        ),
        pk=notification_id,
    )
    notification.feedback_prompt_dismissed_at = timezone.now()
    notification.save(update_fields=['feedback_prompt_dismissed_at'])
    return JsonResponse({'success': True})


@login_required
@require_GET
def api_notifications(request):
    user = request.user
    if not (
        user.is_site_admin or user.is_superuser or user.is_client
    ):
        raise PermissionDenied('Notifications are available to portal users only.')

    sync_scheduled_notifications(user)
    notifications = list(
        Notification.objects.filter(recipient=user)
        .select_related('site')[:30]
    )
    unread_count = Notification.objects.filter(
        recipient=user,
        read_at__isnull=True,
    ).count()
    return JsonResponse({
        'unread_count': unread_count,
        'notifications': [
            {
                'id': item.id,
                'kind': item.kind,
                'title': item.title,
                'message': item.message,
                'url': item.url,
                'created_at': item.created_at.isoformat(),
                'is_read': item.read_at is not None,
            }
            for item in notifications
        ],
    })


@login_required
@require_POST
def api_mark_notification_read(request):
    user = request.user
    if not (user.is_site_admin or user.is_superuser or user.is_client):
        raise PermissionDenied('Notifications are available to portal users only.')
    notification_id = request.POST.get('notification_id')
    if not notification_id:
        return HttpResponseBadRequest('notification_id is required')
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=user,
    )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def api_mark_all_notifications_read(request):
    user = request.user
    if not (user.is_site_admin or user.is_superuser or user.is_client):
        raise PermissionDenied('Notifications are available to portal users only.')
    Notification.objects.filter(
        recipient=user,
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    return JsonResponse({'success': True})


# ==============================================================================
# DYNAMIC TOGGLE & PROGRESS APIS (AJAX & Standard POST)
# ==============================================================================

@site_admin_required
@require_POST
def api_toggle_task(request):
    """
    Toggles a SiteTask completion state and recalculates category & site progress.
    Supports both JSON request and standard form submission.
    """
    is_json = request.content_type == 'application/json'
    if is_json:
        try:
            data = json.loads(request.body)
            task_id = data.get('task_id')
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
    else:
        task_id = request.POST.get('task_id')

    if not task_id:
        return JsonResponse({'success': False, 'error': 'task_id is required'}, status=400)

    task = get_object_or_404(
        SiteTask.objects.select_related('site_category__site', 'site_category__category'),
        id=task_id
    )

    # Toggle task
    task.is_completed = not task.is_completed
    task.save()  # Signal triggers category.recalculate_from_tasks()

    site = task.site_category.site
    overall_progress = site.calculate_overall_progress()

    if is_json:
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'is_completed': task.is_completed,
            'completed_date': task.completed_date.strftime('%b %d, %Y') if task.completed_date else '',
            'category_id': task.site_category.id,
            'category_progress': float(task.site_category.progress_percentage),
            'completed_tasks': task.site_category.completed_tasks_count,
            'total_tasks': task.site_category.total_tasks_count,
            'overall_progress': float(overall_progress),
        })

    messages.success(request, f"Task '{task.task_name}' updated.")
    return redirect('projects:admin_site_detail', site_id=site.id)


@site_admin_required
@require_POST
def api_toggle_category(request):
    """
    Enables or disables an optional WorkCategory for a site.
    Mandatory categories cannot be disabled.
    """
    is_json = request.content_type == 'application/json'
    if is_json:
        try:
            data = json.loads(request.body)
            category_progress_id = data.get('category_progress_id')
            is_enabled = data.get('is_enabled')
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
    else:
        category_progress_id = request.POST.get('category_progress_id')
        is_enabled = request.POST.get('is_enabled') in ['true', '1', 'on', True]

    scp = get_object_or_404(
        SiteCategoryProgress.objects.select_related('category', 'site'),
        id=category_progress_id
    )

    if scp.category.is_mandatory and not is_enabled:
        return JsonResponse({
            'success': False,
            'error': 'Mandatory categories (Building, Electrical, Plumbing) cannot be disabled.'
        }, status=400)

    scp.is_enabled = bool(is_enabled)
    scp.save(update_fields=['is_enabled', 'updated_at'])

    overall_progress = scp.site.calculate_overall_progress()

    if is_json:
        return JsonResponse({
            'success': True,
            'category_progress_id': scp.id,
            'category_name': scp.category.name,
            'is_enabled': scp.is_enabled,
            'category_progress': float(scp.progress_percentage),
            'overall_progress': float(overall_progress),
        })

    messages.success(request, f"Category '{scp.category.name}' state updated.")
    return redirect('projects:admin_site_detail', site_id=scp.site.id)


@site_admin_required
@require_POST
def api_update_category_percentage(request):
    """
    Allows admin to directly adjust category progress percentage (0 - 100).
    """
    is_json = request.content_type == 'application/json'
    if is_json:
        try:
            data = json.loads(request.body)
            category_progress_id = data.get('category_progress_id')
            percentage = Decimal(str(data.get('percentage', 0)))
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid format'}, status=400)
    else:
        category_progress_id = request.POST.get('category_progress_id')
        percentage = Decimal(str(request.POST.get('percentage', 0)))

    # Clamp between 0 and 100
    percentage = max(Decimal('0.00'), min(Decimal('100.00'), percentage))

    scp = get_object_or_404(SiteCategoryProgress.objects.select_related('site'), id=category_progress_id)
    scp.progress_percentage = percentage
    scp.save(update_fields=['progress_percentage', 'updated_at'])

    overall_progress = scp.site.calculate_overall_progress()

    if is_json:
        return JsonResponse({
            'success': True,
            'category_progress_id': scp.id,
            'category_progress': float(scp.progress_percentage),
            'overall_progress': float(overall_progress),
        })

    messages.success(request, f"Updated percentage for {scp.category.name} to {percentage}%.")
    return redirect('projects:admin_site_detail', site_id=scp.site.id)


# ==============================================================================
# CLIENT PORTAL VIEWS (ZERO-TRUST ISOLATION)
# ==============================================================================

@client_required
def client_dashboard(request):
    """
    Client entry point. Automatically resolves client's authorized construction site.
    """
    user_sites = request.user.assigned_sites.all()
    if not user_sites.exists():
        return render(request, 'client_portal/no_site.html', {
            'user': request.user
        })

    site = user_sites.first()
    return redirect('projects:client_site_detail', site_id=site.id)


@client_required
def client_site_detail(request, site_id):
    """
    Client-specific read-only dashboard.
    Strict Zero-Trust validation:
    A client may ONLY access their own assigned construction project.
    """
    site = _get_authorized_client_site(
        request,
        site_id,
        prefetch_related=(
            'category_progresses__category',
            'category_progresses__tasks',
        ),
    )

    overall_progress = site.calculate_overall_progress()
    remaining_progress = site.remaining_percentage

    # Enabled categories only
    enabled_categories = site.category_progresses.filter(is_enabled=True)

    # Prepare serialized data for Chart.js
    chart_category_labels = [cp.category.name for cp in enabled_categories]
    chart_category_data = [float(cp.progress_percentage) for cp in enabled_categories]

    context = {
        'site': site,
        'overall_progress': float(overall_progress),
        'remaining_progress': float(remaining_progress),
        'enabled_categories': enabled_categories,
        'chart_category_labels_json': json.dumps(chart_category_labels),
        'chart_category_data_json': json.dumps(chart_category_data),
        'photo_count': site.update_images.count(),
    }
    return render(request, 'client_portal/dashboard.html', context)


def _get_authorized_client_site(request, site_id, prefetch_related=()):
    site = get_object_or_404(
        ConstructionSite.objects.select_related('client').prefetch_related(
            *prefetch_related
        ),
        id=site_id,
    )
    if site.client_id != request.user.id and not request.user.is_superuser:
        raise PermissionDenied(
            "Access Denied: You are not authorized to view this construction project."
        )
    return site


@client_required
def client_site_work(request, site_id):
    site = _get_authorized_client_site(
        request,
        site_id,
        prefetch_related=('category_progresses__category', 'category_progresses__tasks'),
    )
    return render(request, 'client_portal/work.html', {
        'site': site,
        'enabled_categories': site.category_progresses.filter(is_enabled=True),
        'client_active': 'work',
    })


@client_required
def client_site_updates(request, site_id):
    site = _get_authorized_client_site(
        request,
        site_id,
        prefetch_related=('update_images__category',),
    )
    photos = list(site.update_images.all()[:30])
    return render(request, 'client_portal/updates.html', {
        'site': site,
        'photos': photos,
        'photo_count': site.update_images.count(),
        'client_active': 'updates',
    })


# ==============================================================================
# CLIENT MANAGEMENT (ADMIN ONLY)
# ==============================================================================

@site_admin_required
def admin_client_list(request):
    """
    List all registered clients, their contact information, and assigned construction sites.
    """
    clients = User.objects.filter(is_client=True).prefetch_related('assigned_sites')
    return render(request, 'admin_portal/client_list.html', {
        'clients': clients,
        'total_clients': clients.count()
    })


@site_admin_required
def admin_client_create(request):
    """
    Create a new client with credentials.
    Supports ?next= param to redirect back to site creation.
    """
    next_url = request.GET.get('next', '')
    if request.method == 'POST':
        form = ClientCreationForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Client '{client.get_full_name() or client.username}' created successfully!")
            if next_url:
                return redirect(next_url)
            return redirect('projects:admin_client_list')
    else:
        form = ClientCreationForm()

    return render(request, 'admin_portal/client_form.html', {
        'form': form,
        'next_url': next_url,
        'title': 'Create New Client'
    })


@site_admin_required
@require_POST
def admin_send_client_portal_access(request, client_id):
    client = get_object_or_404(User, pk=client_id, is_client=True)
    try:
        validate_email(client.email)
    except ValidationError:
        messages.error(
            request,
            f"Add a valid email address for {client.get_full_name() or client.username} first.",
        )
        return redirect(f"{reverse('projects:admin_client_list')}#client-{client.id}")

    uid = urlsafe_base64_encode(force_bytes(client.pk))
    token = default_token_generator.make_token(client)
    setup_url = f"{settings.PUBLIC_BASE_URL}{reverse(
        'accounts:client_password_setup',
        kwargs={'uidb64': uid, 'token': token},
    )}"
    body = (
        f"Hello {client.first_name or client.username},\n\n"
        "Your Structura client portal account is ready.\n\n"
        f"Username: {client.username}\n"
        "Set your password using this time-limited link:\n"
        f"{setup_url}\n\n"
        f"After setting your password, sign in at {settings.PUBLIC_BASE_URL}{reverse('accounts:login')}.\n"
        "If you did not expect this message, contact your project administrator."
    )

    try:
        sent_count = send_mail(
            subject='Your Structura client portal access',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[client.email],
            fail_silently=False,
        )
    except (OSError, smtplib.SMTPException):
        logger.exception('Could not send client portal access email to client %s.', client.pk)
        messages.error(
            request,
            'The portal access email could not be sent. Check the email server settings and try again.',
        )
    else:
        if sent_count == 1:
            messages.success(
                request,
                f"Portal access email sent to {client.email}.",
            )
        else:
            messages.error(
                request,
                'The email service did not accept the portal access message.',
            )

    return redirect(f"{reverse('projects:admin_client_list')}#client-{client.id}")


@site_admin_required
@require_POST
def api_create_client(request):
    """
    AJAX endpoint for creating a new client on-the-fly directly from the site creation form.
    Returns JSON with the new client's ID and display label to append to the dropdown.
    """
    is_json = request.content_type == 'application/json'
    if is_json:
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
    else:
        data = request.POST

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone_number', '').strip()
    password = data.get('password', '').strip()

    if not username:
        return JsonResponse({'success': False, 'error': 'Username is required'}, status=400)
    if not password:
        return JsonResponse({'success': False, 'error': 'Password is required'}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({'success': False, 'error': f"Username '{username}' is already taken"}, status=400)

    try:
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_client=True,
            phone_number=phone,
        )
        return JsonResponse({
            'success': True,
            'client': {
                'id': user.id,
                'username': user.username,
                'name': user.get_full_name() or user.username,
                'label': str(user)
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


