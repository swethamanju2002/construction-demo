import os
from decimal import Decimal
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont
import io

from accounts.models import User
from projects.models import (
    WorkCategory,
    ConstructionSite,
    SiteCategoryProgress,
    SiteTask,
    ProjectUpdateImage,
)
from projects.signals import ensure_master_categories


def create_demo_image(title: str, category_name: str, site_name: str, color_hex: str) -> ContentFile:
    """
    Generates a high-quality demonstration site update image with architectural branding.
    """
    width, height = 900, 600
    img = Image.new('RGB', (width, height), color='#10243A')
    draw = ImageDraw.Draw(img)

    # Architectural grid background
    grid_color = '#1A3654'
    for x in range(0, width, 40):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, 40):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Accent header band
    draw.rectangle([(0, 0), (width, 80)], fill='#0B1928')
    draw.rectangle([(0, 78), (width, 82)], fill=color_hex)

    # Header text
    draw.text((30, 25), "STRUCTURA CRM - VERIFIED SITE TELEMETRY", fill='#F5A623')
    draw.text((680, 25), timezone.now().strftime("%Y-%m-%d %H:%M"), fill='#94A3B8')

    # Central blueprint container
    draw.rectangle([(60, 130), (width - 60, height - 90)], outline=color_hex, width=2)
    draw.rectangle([(80, 150), (width - 80, height - 110)], fill='#162E48')

    # Watermark Stamp
    draw.text((100, 180), f"PROJECT: {site_name.upper()}", fill='#FFFFFF')
    draw.text((100, 220), f"WORK CATEGORY: {category_name.upper()}", fill='#38BDF8')
    draw.text((100, 260), f"INSPECTION RECORD: {title}", fill='#FFFFFF')
    
    # Progress badge box
    draw.rectangle([(100, 320), (380, 370)], fill=color_hex)
    draw.text((120, 336), "VERIFIED INSPECTION PASS", fill='#10243A')

    # Footer notice
    draw.text((60, height - 50), "OFFICIAL CONTRACTOR CERTIFIED REPORT • GEO-TAGGED ON-SITE CAPTURE", fill='#64748B')

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=90)
    return ContentFile(buffer.getvalue(), name=f"{title.lower().replace(' ', '_')}.jpg")


class Command(BaseCommand):
    help = "Seeds database with realistic construction sites, categories, subtasks, clients, and photos."

    def handle(self, *args, **options):
        self.stdout.write("Seeding master categories and default subtasks...")
        ensure_master_categories()

        # 1. Superuser / Site Administrator
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@structura.com',
                'first_name': 'Marcus',
                'last_name': 'Kane (PE)',
                'is_site_admin': True,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('admin123')
        admin_user.is_site_admin = True
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        self.stdout.write(f"Admin account: {admin_user.username} / admin123")

        # 2. Client Users
        client_john, _ = User.objects.get_or_create(
            username='john_client',
            defaults={
                'email': 'john@skylinevilla.com',
                'first_name': 'John & Claire',
                'last_name': 'Sterling',
                'is_client': True,
                'phone_number': '+1 (555) 482-9912',
            }
        )
        client_john.set_password('client123')
        client_john.is_client = True
        client_john.save()

        client_sarah, _ = User.objects.get_or_create(
            username='sarah_client',
            defaults={
                'email': 'sarah@oakridgehub.com',
                'first_name': 'Sarah',
                'last_name': 'Jenkins',
                'company_name': 'Oakridge Commercial Group',
                'is_client': True,
                'phone_number': '+1 (555) 723-1104',
            }
        )
        client_sarah.set_password('client123')
        client_sarah.is_client = True
        client_sarah.save()
        self.stdout.write(f"Client accounts: {client_john.username} / client123 and {client_sarah.username} / client123")

        # 3. Construction Site 1: Skyline Villa (5 Categories enabled, 70% Progress)
        today = timezone.now().date()
        site1, _ = ConstructionSite.objects.get_or_create(
            name='Skyline Villa Residence',
            client=client_john,
            defaults={
                'site_address': 'Plot 42, Grand Crest Ridge, North Hills Vista, CA 90210',
                'start_date': today - timezone.timedelta(days=90),
                'estimated_completion_date': today + timezone.timedelta(days=75),
                'status': ConstructionSite.STATUS_ONGOING,
                'project_manager': 'Eng. Robert Vance (Senior Structural Lead)',
            }
        )

        # Enable optional categories for Site 1
        showcase_cp = site1.category_progresses.get(category__slug='showcase-work')
        showcase_cp.is_enabled = True
        showcase_cp.save()

        wall_cp = site1.category_progresses.get(category__slug='wall-ceiling-work')
        wall_cp.is_enabled = True
        wall_cp.save()

        # Check off realistic subtasks for Site 1
        # Building (4 tasks): Basement, Lintel, Roof Concrete checked (3 of 4 = 75%)
        building_cp = site1.category_progresses.get(category__slug='building-work')
        for task in building_cp.tasks.filter(task_name__in=['Basement', 'Lintel', 'Roof Concrete']):
            task.is_completed = True
            task.save()

        # Electrical (3 tasks): Wiring Pipe Concealing, Wiring checked (2 of 3 = 66.67%)
        electrical_cp = site1.category_progresses.get(category__slug='electrical-work')
        for task in electrical_cp.tasks.filter(task_name__in=['Wiring Pipe Concealing', 'Wiring']):
            task.is_completed = True
            task.save()

        # Plumbing (4 tasks): Pipe Concealing, Input/Output, Tank Fixing checked (3 of 4 = 75%)
        plumbing_cp = site1.category_progresses.get(category__slug='plumbing-work')
        for task in plumbing_cp.tasks.filter(task_name__in=['Water Line Pipe Concealing', 'Water Input & Output Pipe Fitting', 'Water Tank Fixing']):
            task.is_completed = True
            task.save()

        # Showcase (3 tasks): Planning, Base Fitting checked (2 of 3 = 66.67%)
        for task in showcase_cp.tasks.filter(task_name__in=['Planning', 'Base Fitting']):
            task.is_completed = True
            task.save()

        # Wall Ceiling (3 tasks): Planning, Channel Fitting checked (2 of 3 = 66.67%)
        for task in wall_cp.tasks.filter(task_name__in=['Planning', 'Channel Fitting']):
            task.is_completed = True
            task.save()

        # 4. Construction Site 2: Oakridge Commercial Complex (3 Mandatory only, 44.44% Progress)
        site2, _ = ConstructionSite.objects.get_or_create(
            name='Oakridge Commercial Complex',
            client=client_sarah,
            defaults={
                'site_address': '880 Enterprise Boulevard, Tech Park Sector 4',
                'start_date': today - timezone.timedelta(days=45),
                'estimated_completion_date': today + timezone.timedelta(days=160),
                'status': ConstructionSite.STATUS_ONGOING,
                'project_manager': 'Eng. David Sterling (M.Sc Civil Systems)',
            }
        )
        # Ensure optional are disabled on Site 2
        site2.category_progresses.filter(category__slug__in=['showcase-work', 'wall-ceiling-work']).update(is_enabled=False)

        # Building: 2 of 4 (50%)
        b2 = site2.category_progresses.get(category__slug='building-work')
        for t in b2.tasks.filter(task_name__in=['Basement', 'Lintel']):
            t.is_completed = True
            t.save()

        # Electrical: 1 of 3 (33.33%)
        e2 = site2.category_progresses.get(category__slug='electrical-work')
        for t in e2.tasks.filter(task_name__in=['Wiring Pipe Concealing']):
            t.is_completed = True
            t.save()

        # Plumbing: 2 of 4 (50%)
        p2 = site2.category_progresses.get(category__slug='plumbing-work')
        for t in p2.tasks.filter(task_name__in=['Water Line Pipe Concealing', 'Water Input & Output Pipe Fitting']):
            t.is_completed = True
            t.save()

        # 5. Construction Site 3: Aura Modern Penthouse (Completed Build)
        site3, _ = ConstructionSite.objects.get_or_create(
            name='Aura Penthouse Tower',
            client=client_john,
            defaults={
                'site_address': '12 Oceanview Promenade, Coastal District',
                'start_date': today - timezone.timedelta(days=240),
                'estimated_completion_date': today - timezone.timedelta(days=15),
                'status': ConstructionSite.STATUS_COMPLETED,
                'project_manager': 'Elena Rostova, AIA',
            }
        )
        # Mark all tasks completed for Site 3
        for cp in site3.category_progresses.all():
            cp.is_enabled = True
            cp.save()
            for t in cp.tasks.all():
                t.is_completed = True
                t.save()

        # 6. Add Demo Site Photos
        if not ProjectUpdateImage.objects.filter(site=site1).exists():
            photos_data = [
                (
                    "Reinforced concrete roof slab casting inspection passed",
                    building_cp.category,
                    "#1769AA"
                ),
                (
                    "Concealed fire-retardant wiring pipe routing across zone 2",
                    electrical_cp.category,
                    "#F5A623"
                ),
                (
                    "Dual-pressure test completed on main water manifold line",
                    plumbing_cp.category,
                    "#0284C7"
                ),
                (
                    "Modular hardwood base frames fitted for display showcase",
                    showcase_cp.category,
                    "#8B5CF6"
                ),
                (
                    "Acoustic false ceiling perimeter steel channel alignment",
                    wall_cp.category,
                    "#EC4899"
                ),
            ]

            for caption, cat, hex_col in photos_data:
                img_file = create_demo_image(caption, cat.name, site1.name, hex_col)
                p = ProjectUpdateImage(site=site1, category=cat, caption=caption)
                p.image.save(img_file.name, img_file, save=True)

        self.stdout.write(self.style.SUCCESS("Demo database successfully seeded with sites, tasks, clients, and photos!"))
