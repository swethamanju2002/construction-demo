from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ConstructionSite, WorkCategory, SiteCategoryProgress, SiteTask

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
