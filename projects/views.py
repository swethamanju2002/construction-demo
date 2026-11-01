import json
from decimal import Decimal
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Avg
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from accounts.models import User
from accounts.forms import ClientCreationForm
from accounts.permissions import site_admin_required, client_required
from .forms import ConstructionSiteForm, ProjectUpdateImageForm
from .models import (
    ConstructionSite,
    WorkCategory,
    SiteCategoryProgress,
    SiteTask,
    ProjectUpdateImage,
    SiteProgressHistory,
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
    total_sites = len(sites)
    ongoing_count = sum(1 for s in sites if s.status == ConstructionSite.STATUS_ONGOING)
    completed_count = sum(1 for s in sites if s.status == ConstructionSite.STATUS_COMPLETED)
    planning_count = sum(1 for s in sites if s.status == ConstructionSite.STATUS_PLANNING)
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
        form = ConstructionSiteForm()

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
    site = get_object_or_404(
        ConstructionSite.objects.select_related('client').prefetch_related(
            'category_progresses__category',
            'category_progresses__tasks',
            'update_images__category'
        ),
        id=site_id
    )

    # Server-side Zero-Trust Access Check
    if site.client != request.user and not request.user.is_superuser:
        raise PermissionDenied("Access Denied: You are not authorized to view this construction project.")

    overall_progress = site.calculate_overall_progress()
    remaining_progress = site.remaining_percentage

    # Enabled categories only
    enabled_categories = site.category_progresses.filter(is_enabled=True)

    # Prepare serialized data for Chart.js
    chart_category_labels = [cp.category.name for cp in enabled_categories]
    chart_category_data = [float(cp.progress_percentage) for cp in enabled_categories]

    recent_photos = site.update_images.all()[:30]

    context = {
        'site': site,
        'overall_progress': float(overall_progress),
        'remaining_progress': float(remaining_progress),
        'enabled_categories': enabled_categories,
        'chart_category_labels_json': json.dumps(chart_category_labels),
        'chart_category_data_json': json.dumps(chart_category_data),
        'photos': recent_photos,
    }
    return render(request, 'client_portal/dashboard.html', context)


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


