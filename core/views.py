from django.contrib import messages
from django.shortcuts import render, redirect
from projects.models import ConstructionSite, ProjectUpdateImage, WorkCategory
from .forms import ContactInquiryForm


def home(request):
    """
    Public Homepage: Hero, Company Intro, Key Statistics, Featured Builds, Process Lifecycle, and Contact CTA.
    """
    completed_sites = ConstructionSite.objects.filter(status=ConstructionSite.STATUS_COMPLETED)[:3]
    active_sites = ConstructionSite.objects.filter(status=ConstructionSite.STATUS_ONGOING)[:3]
    recent_photos = ProjectUpdateImage.objects.select_related('category', 'site')[:6]

    # Real data metrics
    total_sites = ConstructionSite.objects.count()
    completed_count = ConstructionSite.objects.filter(status=ConstructionSite.STATUS_COMPLETED).count()
    category_count = WorkCategory.objects.count()

    context = {
        'completed_sites': completed_sites,
        'active_sites': active_sites,
        'recent_photos': recent_photos,
        'total_sites': total_sites,
        'completed_count': completed_count,
        'category_count': category_count,
    }
    return render(request, 'public/home.html', context)


def about(request):
    """
    About Us: Company profile, engineering philosophy, safety standards, and project methodology.
    """
    return render(request, 'public/about.html')


def gallery(request):
    """
    Project Gallery: Filterable showcase of verified site updates and completed structures with lightbox.
    """
    category_slug = request.GET.get('category', '').strip()
    categories = WorkCategory.objects.all()

    photos_qs = ProjectUpdateImage.objects.select_related('site', 'category').all()
    if category_slug:
        photos_qs = photos_qs.filter(category__slug=category_slug)

    context = {
        'photos': photos_qs,
        'categories': categories,
        'active_category': category_slug,
    }
    return render(request, 'public/gallery.html', context)


def contact(request):
    """
    Contact Us: Form with validation, company contact information, and consultation request.
    """
    if request.method == 'POST':
        form = ContactInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save()
            messages.success(
                request,
                f"Thank you, {inquiry.name}! Your inquiry regarding '{inquiry.subject}' has been submitted. Our project team will respond within 24 hours."
            )
            return redirect('core:contact')
    else:
        form = ContactInquiryForm()

    return render(request, 'public/contact.html', {'form': form})

