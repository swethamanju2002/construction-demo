from decimal import Decimal
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from core.models import ContactInquiry
from projects.models import (
    ClientFeedback,
    ConstructionSite,
    Notification,
    ProjectUpdateImage,
    WorkCategory,
    SiteCategoryProgress,
    SiteTask,
)
from projects.forms import ConstructionSiteForm


class ProgressCalculationTests(TestCase):
    def setUp(self):
        # Create client user
        self.client_user = User.objects.create_user(
            username='testclient',
            email='client@test.com',
            password='Password123!',
            is_client=True
        )

        # Create construction site - trigger post_save signals
        self.site = ConstructionSite.objects.create(
            name='Oceanview Villa Project',
            client=self.client_user,
            site_address='100 Ocean Drive, Coastal Bay',
            start_date=timezone.now().date(),
            estimated_completion_date=timezone.now().date() + timezone.timedelta(days=180),
            status=ConstructionSite.STATUS_ONGOING
        )

    def test_auto_population_of_categories_and_tasks(self):
        """
        Verify that creating a site automatically populates:
        - 5 categories (3 mandatory enabled, 2 optional disabled)
        - Predefined subtasks for each category
        """
        category_progresses = self.site.category_progresses.all()
        self.assertEqual(category_progresses.count(), 5)

        # Mandatory categories must be enabled
        mandatory_slugs = ['building-work', 'electrical-work', 'plumbing-work']
        for slug in mandatory_slugs:
            cp = category_progresses.get(category__slug=slug)
            self.assertTrue(cp.is_enabled, f"{slug} should be enabled by default")
            self.assertEqual(cp.progress_percentage, Decimal('0.00'))

        # Optional categories must be disabled
        optional_slugs = ['showcase-work', 'wall-ceiling-work']
        for slug in optional_slugs:
            cp = category_progresses.get(category__slug=slug)
            self.assertFalse(cp.is_enabled, f"{slug} should be disabled by default")
            self.assertEqual(cp.progress_percentage, Decimal('0.00'))

        # Verify task checklist counts
        building_cp = category_progresses.get(category__slug='building-work')
        self.assertEqual(building_cp.tasks.count(), 4)
        expected_building_tasks = ['Basement', 'Lintel', 'Roof Concrete', 'Finishing Touch']
        self.assertListEqual(
            list(building_cp.tasks.values_list('task_name', flat=True)),
            expected_building_tasks
        )

        electrical_cp = category_progresses.get(category__slug='electrical-work')
        self.assertEqual(electrical_cp.tasks.count(), 3)

        plumbing_cp = category_progresses.get(category__slug='plumbing-work')
        self.assertEqual(plumbing_cp.tasks.count(), 4)

        showcase_cp = category_progresses.get(category__slug='showcase-work')
        self.assertEqual(showcase_cp.tasks.count(), 3)

        wall_cp = category_progresses.get(category__slug='wall-ceiling-work')
        self.assertEqual(wall_cp.tasks.count(), 3)

    def test_three_mandatory_categories_calculation(self):
        """
        Test blueprint example 1:
        Building Work = 60%, Electrical Work = 40%, Plumbing Work = 75%.
        Optional categories disabled.
        Overall Progress = (60 + 40 + 75) / 3 = 175 / 3 = 58.33%
        """
        building = self.site.category_progresses.get(category__slug='building-work')
        electrical = self.site.category_progresses.get(category__slug='electrical-work')
        plumbing = self.site.category_progresses.get(category__slug='plumbing-work')

        building.progress_percentage = Decimal('60.00')
        building.save()

        electrical.progress_percentage = Decimal('40.00')
        electrical.save()

        plumbing.progress_percentage = Decimal('75.00')
        plumbing.save()

        # Ensure optional are disabled
        showcase = self.site.category_progresses.get(category__slug='showcase-work')
        showcase.progress_percentage = Decimal('30.00')
        showcase.is_enabled = False
        showcase.save()

        wall = self.site.category_progresses.get(category__slug='wall-ceiling-work')
        wall.progress_percentage = Decimal('50.00')
        wall.is_enabled = False
        wall.save()

        overall = self.site.calculate_overall_progress()
        self.assertEqual(overall, Decimal('58.33'))

    def test_five_categories_all_enabled_calculation(self):
        """
        Test blueprint example 2:
        Building: 60%, Electrical: 40%, Plumbing: 75%, Showcase: 30%, Wall Ceiling: 50%.
        All 5 enabled.
        Overall Progress = (60 + 40 + 75 + 30 + 50) / 5 = 255 / 5 = 51.67%
        """
        building = self.site.category_progresses.get(category__slug='building-work')
        electrical = self.site.category_progresses.get(category__slug='electrical-work')
        plumbing = self.site.category_progresses.get(category__slug='plumbing-work')
        showcase = self.site.category_progresses.get(category__slug='showcase-work')
        wall = self.site.category_progresses.get(category__slug='wall-ceiling-work')

        building.progress_percentage = Decimal('60.00')
        building.save()

        electrical.progress_percentage = Decimal('40.00')
        electrical.save()

        plumbing.progress_percentage = Decimal('75.00')
        plumbing.save()

        showcase.progress_percentage = Decimal('30.00')
        showcase.is_enabled = True
        showcase.save()

        wall.progress_percentage = Decimal('50.00')
        wall.is_enabled = True
        wall.save()

        overall = self.site.calculate_overall_progress()
        # (60 + 40 + 75 + 30 + 50) / 5 = 255 / 5 = 51.00%
        self.assertEqual(overall, Decimal('51.00'))

        # Also test with wall ceiling at 53.33% yielding 51.67%
        wall.progress_percentage = Decimal('53.33')
        wall.save()
        overall_with_53 = self.site.calculate_overall_progress()
        self.assertEqual(overall_with_53, Decimal('51.67'))


    def test_task_checklist_completion_dynamic_recalculation(self):
        """
        Verify that marking tasks complete dynamically recalculates category progress.
        Building Work has 4 tasks:
        - 1 completed -> 25.00%
        - 2 completed -> 50.00%
        - 3 completed -> 75.00%
        - 4 completed -> 100.00%
        """
        building = self.site.category_progresses.get(category__slug='building-work')
        tasks = list(building.tasks.all())
        self.assertEqual(len(tasks), 4)

        # Mark 1 task completed
        tasks[0].is_completed = True
        tasks[0].save()
        building.refresh_from_db()
        self.assertEqual(building.progress_percentage, Decimal('25.00'))

        # Mark 2nd task completed
        tasks[1].is_completed = True
        tasks[1].save()
        building.refresh_from_db()
        self.assertEqual(building.progress_percentage, Decimal('50.00'))

        # Uncheck 1st task
        tasks[0].is_completed = False
        tasks[0].save()
        building.refresh_from_db()
        self.assertEqual(building.progress_percentage, Decimal('25.00'))

    def test_disabled_optional_categories_not_in_denominator(self):
        """
        Verify that when an optional category is disabled, it is strictly excluded
        from both sum and denominator.
        """
        building = self.site.category_progresses.get(category__slug='building-work')
        electrical = self.site.category_progresses.get(category__slug='electrical-work')
        plumbing = self.site.category_progresses.get(category__slug='plumbing-work')
        showcase = self.site.category_progresses.get(category__slug='showcase-work')

        building.progress_percentage = Decimal('100.00')
        building.save()
        electrical.progress_percentage = Decimal('100.00')
        electrical.save()
        plumbing.progress_percentage = Decimal('100.00')
        plumbing.save()

        # Overall should be 100.00% with 3 mandatory
        self.assertEqual(self.site.calculate_overall_progress(), Decimal('100.00'))

        # If showcase is enabled with 0%, overall should drop to (300/4) = 75.00%
        showcase.is_enabled = True
        showcase.progress_percentage = Decimal('0.00')
        showcase.save()
        self.assertEqual(self.site.calculate_overall_progress(), Decimal('75.00'))

        # When showcase is disabled again, it must return to 100.00%
        showcase.is_enabled = False
        showcase.save()
        self.assertEqual(self.site.calculate_overall_progress(), Decimal('100.00'))

    def test_registration_form_saves_optional_categories(self):
        form = ConstructionSiteForm(data={
            'name': 'Category Selection Test',
            'client': self.client_user.id,
            'site_address': '25 Test Avenue',
            'start_date': timezone.now().date(),
            'estimated_completion_date': timezone.now().date() + timezone.timedelta(days=120),
            'status': ConstructionSite.STATUS_ONGOING,
            'project_manager': 'Test Project Lead',
            'showcase_work': 'on',
            'wall_ceiling_work': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

        site = form.save()
        self.assertTrue(
            site.category_progresses.get(category__slug='showcase-work').is_enabled
        )
        self.assertFalse(
            site.category_progresses.get(category__slug='wall-ceiling-work').is_enabled
        )
        for slug in ('building-work', 'electrical-work', 'plumbing-work'):
            self.assertTrue(
                site.category_progresses.get(category__slug=slug).is_enabled
            )


class PortalPageRenderingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='portaladmin',
            password='PortalPassword123!',
            is_site_admin=True,
        )
        self.client_user = User.objects.create_user(
            username='portalclient',
            password='PortalPassword123!',
            is_client=True,
        )
        self.site = ConstructionSite.objects.create(
            name='Portal Rendering Site',
            client=self.client_user,
            site_address='10 Construction Way',
            start_date=timezone.now().date(),
            estimated_completion_date=timezone.now().date() + timezone.timedelta(days=90),
            status=ConstructionSite.STATUS_ONGOING,
        )

    def test_admin_pages_render_with_shared_portal_navigation(self):
        self.client.force_login(self.admin)
        paths = [
            '/admin-portal/dashboard/',
            '/admin-portal/site/create/',
            f'/admin-portal/site/{self.site.id}/',
            f'/admin-portal/site/{self.site.id}/edit/',
            '/admin-portal/clients/',
            '/admin-portal/clients/create/',
            '/admin-portal/inquiries/',
            '/admin-portal/feedback/',
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'adminSidebar')
                self.assertContains(response, 'adminMenuToggle')
                self.assertContains(response, 'data-notification-center')

    def test_client_directory_site_assignment_prefills_client(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f'/admin-portal/site/create/?client={self.client_user.id}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['form']['client'].value(),
            self.client_user.id,
        )

    def test_client_dashboard_remains_read_only_and_renders_project_data(self):
        self.client.force_login(self.client_user)
        response = self.client.get('/client-portal/dashboard/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'client-project-hero')
        self.assertContains(response, 'data-notification-center')
        self.assertContains(response, self.site.name)
        self.assertContains(response, 'overallProgressDonut')
        self.assertNotContains(response, 'task-toggle-checkbox')

    def test_unassigned_client_sees_portal_pending_state(self):
        unassigned_client = User.objects.create_user(
            username='unassignedportalclient',
            password='PortalPassword123!',
            is_client=True,
        )
        self.client.force_login(unassigned_client)
        response = self.client.get('/client-portal/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'client-unassigned-page')
        self.assertContains(response, 'client-sidebar')


class NotificationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='notificationadmin',
            password='PortalPassword123!',
            is_site_admin=True,
        )
        self.client_user = User.objects.create_user(
            username='notificationclient',
            password='PortalPassword123!',
            is_client=True,
        )
        self.other_client = User.objects.create_user(
            username='othernotificationclient',
            password='PortalPassword123!',
            is_client=True,
        )
        self.site = ConstructionSite.objects.create(
            name='Notification Test Site',
            client=self.client_user,
            site_address='20 Notification Road',
            start_date=timezone.localdate(),
            estimated_completion_date=timezone.localdate() + timedelta(days=90),
            status=ConstructionSite.STATUS_ONGOING,
        )

    def test_progress_photo_status_schedule_and_inquiry_events(self):
        building = self.site.category_progresses.get(
            category__slug='building-work'
        )
        task = building.tasks.first()
        task.is_completed = True
        task.save()
        building.refresh_from_db()
        progress_notice = Notification.objects.get(
            recipient=self.client_user,
            kind=Notification.KIND_TASK_PROGRESS,
            site=self.site,
        )
        self.assertIn('25.00%', progress_notice.message)

        self.site.status = ConstructionSite.STATUS_ON_HOLD
        self.site.estimated_completion_date += timedelta(days=5)
        self.site.save()
        self.assertTrue(Notification.objects.filter(
            recipient=self.client_user,
            kind=Notification.KIND_SITE_STATUS,
            feedback_requested=True,
            site=self.site,
        ).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.client_user,
            kind=Notification.KIND_SCHEDULE_CHANGE,
            feedback_requested=True,
            site=self.site,
        ).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin,
            kind=Notification.KIND_SITE_ALERT,
            site=self.site,
        ).exists())

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                ProjectUpdateImage.objects.create(
                    site=self.site,
                    caption='Foundation progress',
                    image=SimpleUploadedFile(
                        'foundation.jpg',
                        b'not-a-real-image',
                        content_type='image/jpeg',
                    ),
                )
        self.assertTrue(Notification.objects.filter(
            recipient=self.client_user,
            kind=Notification.KIND_PROJECT_UPDATE,
            title='New site photo update',
            feedback_requested=True,
            site=self.site,
        ).exists())

        ContactInquiry.objects.create(
            name='Prospective Client',
            email='prospect@example.com',
            subject='New home build',
            message='Please contact me about a project.',
        )
        inquiry_notice = Notification.objects.get(
            recipient=self.admin,
            kind=Notification.KIND_CONTACT_INQUIRY,
        )
        self.assertIn('/admin-portal/inquiries/#inquiry-', inquiry_notice.url)
        self.client.force_login(self.admin)
        response = self.client.get('/admin-portal/inquiries/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Prospective Client')

    def test_notification_feed_is_private_and_read_state_persists(self):
        client_notice = Notification.objects.create(
            recipient=self.client_user,
            site=self.site,
            kind=Notification.KIND_PROJECT_UPDATE,
            title='Client only update',
            message='A private client message',
            event_key='client-private',
        )
        Notification.objects.create(
            recipient=self.admin,
            site=self.site,
            kind=Notification.KIND_SITE_ALERT,
            title='Admin only update',
            message='A private admin message',
            event_key='admin-private',
        )

        self.client.force_login(self.client_user)
        feed = self.client.get('/admin-portal/api/notifications/')
        self.assertEqual(feed.status_code, 200)
        self.assertContains(feed, 'Client only update')
        self.assertNotContains(feed, 'Admin only update')
        read_response = self.client.post(
            '/admin-portal/api/notifications/read/',
            {'notification_id': client_notice.id},
        )
        self.assertEqual(read_response.status_code, 200)
        client_notice.refresh_from_db()
        self.assertIsNotNone(client_notice.read_at)

        self.client.force_login(self.other_client)
        unauthorized_read = self.client.post(
            '/admin-portal/api/notifications/read/',
            {'notification_id': client_notice.id},
        )
        self.assertEqual(unauthorized_read.status_code, 404)
        client_notice.refresh_from_db()
        self.assertIsNotNone(client_notice.read_at)

    def test_due_date_alerts_are_created_once_on_feed_refresh(self):
        self.site.estimated_completion_date = timezone.localdate() + timedelta(days=3)
        self.site.save(update_fields=['estimated_completion_date'])
        self.client.force_login(self.client_user)
        for _ in range(2):
            response = self.client.get('/admin-portal/api/notifications/')
            self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.client_user,
                kind=Notification.KIND_DUE_DATE,
            ).count(),
            1,
        )

        self.site.estimated_completion_date = timezone.localdate() - timedelta(days=1)
        self.site.save(update_fields=['estimated_completion_date'])
        self.client.force_login(self.client_user)
        missed_date_response = self.client.get('/admin-portal/api/notifications/')
        self.assertEqual(missed_date_response.status_code, 200)
        self.assertTrue(Notification.objects.filter(
            recipient=self.client_user,
            kind=Notification.KIND_DUE_DATE,
            title='Estimated completion date passed',
        ).exists())

        self.client.force_login(self.admin)
        for _ in range(2):
            response = self.client.get('/admin-portal/api/notifications/')
            self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin,
            kind=Notification.KIND_SITE_ALERT,
            title='Project past estimated completion',
        ).exists())
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.admin,
                kind=Notification.KIND_SITE_ALERT,
                title='Project past estimated completion',
            ).count(),
            1,
        )


class ClientFeedbackTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='feedbackadmin',
            password='PortalPassword123!',
            is_site_admin=True,
        )
        self.client_user = User.objects.create_user(
            username='feedbackclient',
            password='PortalPassword123!',
            is_client=True,
        )
        self.other_client = User.objects.create_user(
            username='feedbackother',
            password='PortalPassword123!',
            is_client=True,
        )
        self.site = ConstructionSite.objects.create(
            name='Feedback Test Site',
            client=self.client_user,
            site_address='40 Feedback Avenue',
            start_date=timezone.localdate(),
            estimated_completion_date=timezone.localdate() + timedelta(days=60),
            status=ConstructionSite.STATUS_ONGOING,
        )

    def test_admin_work_update_prompts_client_and_admin_can_read_response(self):
        task = self.site.category_progresses.get(
            category__slug='building-work'
        ).tasks.first()
        task.is_completed = True
        task.save()
        update = Notification.objects.get(
            recipient=self.client_user,
            site=self.site,
            feedback_requested=True,
        )

        self.client.force_login(self.client_user)
        site_response = self.client.get(f'/client-portal/site/{self.site.id}/')
        self.assertEqual(site_response.status_code, 200)
        self.assertContains(site_response, 'client-sidebar')
        self.assertContains(site_response, 'feedback-prompt-overlay')
        pending = self.client.get('/client-portal/api/feedback/pending/')
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.json()['request']['notification_id'], update.id)

        submitted = self.client.post('/client-portal/api/feedback/submit/', {
            'notification_id': update.id,
            'message': 'The progress update looks good.',
        })
        self.assertEqual(submitted.status_code, 200)
        feedback = ClientFeedback.objects.get(update_notification=update)
        self.assertEqual(feedback.author, self.client_user)
        self.assertEqual(feedback.site, self.site)
        self.assertEqual(
            self.client.get('/client-portal/api/feedback/pending/').json()['request'],
            None,
        )

        self.client.force_login(self.admin)
        admin_page = self.client.get('/admin-portal/feedback/')
        self.assertEqual(admin_page.status_code, 200)
        self.assertContains(admin_page, 'The progress update looks good.')
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin,
            kind=Notification.KIND_CLIENT_FEEDBACK,
            url__contains=f'#feedback-{feedback.id}',
        ).exists())
        self.client.post('/admin-portal/feedback/', {
            'feedback_id': feedback.id,
            'is_read': 'true',
        })
        feedback.refresh_from_db()
        self.assertIsNotNone(feedback.admin_read_at)

    def test_client_feedback_page_scopes_projects_and_shows_history(self):
        self.client.force_login(self.client_user)
        page = self.client.get('/client-portal/feedback/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'client-sidebar')
        self.assertContains(page, 'My Feedback')

        submitted = self.client.post('/client-portal/feedback/', {
            'site': self.site.id,
            'message': 'Please share more photos.',
        })
        self.assertEqual(submitted.status_code, 302)
        self.assertEqual(ClientFeedback.objects.count(), 1)

        self.client.force_login(self.other_client)
        unauthorized = self.client.post('/client-portal/feedback/', {
            'site': self.site.id,
            'message': 'Trying to comment on another project.',
        })
        self.assertEqual(unauthorized.status_code, 200)
        self.assertEqual(ClientFeedback.objects.count(), 1)

    def test_client_can_dismiss_feedback_prompt_persistently(self):
        update = Notification.objects.create(
            recipient=self.client_user,
            site=self.site,
            kind=Notification.KIND_TASK_PROGRESS,
            title='Progress changed',
            message='A project task was updated.',
            event_key='feedback-dismiss-test',
            feedback_requested=True,
        )
        self.client.force_login(self.client_user)
        dismissed = self.client.post('/client-portal/api/feedback/dismiss/', {
            'notification_id': update.id,
        })
        self.assertEqual(dismissed.status_code, 200)
        update.refresh_from_db()
        self.assertIsNotNone(update.feedback_prompt_dismissed_at)
        self.assertIsNone(
            self.client.get('/client-portal/api/feedback/pending/').json()['request']
        )

        self.client.force_login(self.other_client)
        unauthorized = self.client.post('/client-portal/api/feedback/dismiss/', {
            'notification_id': update.id,
        })
        self.assertEqual(unauthorized.status_code, 404)

