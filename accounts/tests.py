import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import ContactInquiry
from projects.models import ConstructionSite, SiteCategoryProgress, SiteTask


class SecurityAndPermissionTests(TestCase):
    def setUp(self):
        self.client_runner = Client()

        # 1. Site Admin User
        self.admin_user = User.objects.create_user(
            username='admin_boss',
            email='admin@structura.com',
            password='AdminPassword123!',
            is_site_admin=True
        )

        # 2. Client A User & Site A
        self.client_a = User.objects.create_user(
            username='client_alice',
            email='alice@home.com',
            password='ClientPassword123!',
            is_client=True
        )
        self.site_a = ConstructionSite.objects.create(
            name='Alice Skyline Villa',
            client=self.client_a,
            site_address='101 Skyline Way',
            start_date=timezone.now().date(),
            estimated_completion_date=timezone.now().date() + timezone.timedelta(days=90),
            status=ConstructionSite.STATUS_ONGOING
        )

        # 3. Client B User & Site B
        self.client_b = User.objects.create_user(
            username='client_bob',
            email='bob@commercial.com',
            password='ClientPassword123!',
            is_client=True
        )
        self.site_b = ConstructionSite.objects.create(
            name='Bob Commercial Hub',
            client=self.client_b,
            site_address='202 Commercial Plaza',
            start_date=timezone.now().date(),
            estimated_completion_date=timezone.now().date() + timezone.timedelta(days=120),
            status=ConstructionSite.STATUS_ONGOING
        )

    def test_anonymous_user_redirected_from_protected_portals(self):
        """
        Anonymous users accessing admin or client portals must be redirected to login.
        """
        # Admin dashboard
        res = self.client_runner.get(reverse('projects:admin_dashboard'))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('accounts:login'), res.url)

        # Client dashboard
        res = self.client_runner.get(reverse('projects:client_dashboard'))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('accounts:login'), res.url)

    def test_client_cannot_access_other_clients_site(self):
        """
        Zero-Trust isolation: Client A accessing Client B's site must strictly return 403 Forbidden.
        """
        self.client_runner.login(username='client_alice', password='ClientPassword123!')

        # Client Alice accessing her own site: 200 OK
        res = self.client_runner.get(reverse('projects:client_site_detail', kwargs={'site_id': self.site_a.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alice Skyline Villa')

        # Client Alice attempting to access Client Bob's site: 403 Forbidden
        res = self.client_runner.get(reverse('projects:client_site_detail', kwargs={'site_id': self.site_b.id}))
        self.assertEqual(res.status_code, 403)

    def test_client_cannot_access_admin_dashboard(self):
        """
        A client user must not have access to the site administrator dashboard.
        """
        self.client_runner.login(username='client_alice', password='ClientPassword123!')
        res = self.client_runner.get(reverse('projects:admin_dashboard'))
        self.assertEqual(res.status_code, 403)

    def test_client_read_only_tamper_protection_on_task_api(self):
        """
        Under no circumstances can a client view or trigger updates to task status
        or category percentages.
        """
        self.client_runner.login(username='client_alice', password='ClientPassword123!')

        # Get a task from Alice's site
        building_cp = self.site_a.category_progresses.get(category__slug='building-work')
        task = building_cp.tasks.first()
        self.assertFalse(task.is_completed)

        # Alice attempts to POST to the toggle-task API
        res = self.client_runner.post(
            reverse('projects:api_toggle_task'),
            data=json.dumps({'task_id': task.id}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)

        # Verify task remains unchanged in the database
        task.refresh_from_db()
        self.assertFalse(task.is_completed)

    def test_client_cannot_toggle_optional_categories(self):
        """
        Clients cannot enable or disable optional categories.
        """
        self.client_runner.login(username='client_alice', password='ClientPassword123!')

        showcase_cp = self.site_a.category_progresses.get(category__slug='showcase-work')
        self.assertFalse(showcase_cp.is_enabled)

        res = self.client_runner.post(
            reverse('projects:api_toggle_category'),
            data=json.dumps({'category_progress_id': showcase_cp.id, 'is_enabled': True}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)

        showcase_cp.refresh_from_db()
        self.assertFalse(showcase_cp.is_enabled)

    def test_admin_can_manage_site_and_tasks(self):
        """
        Site admin has full authorization to toggle tasks and categories.
        """
        self.client_runner.login(username='admin_boss', password='AdminPassword123!')

        building_cp = self.site_a.category_progresses.get(category__slug='building-work')
        task = building_cp.tasks.first()

        res = self.client_runner.post(
            reverse('projects:api_toggle_task'),
            data=json.dumps({'task_id': task.id}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_completed'])

        # Verify task is marked completed in DB
        task.refresh_from_db()
        self.assertTrue(task.is_completed)

    def test_public_pages_and_contact_inquiry(self):
        """
        Public pages (Home, About, Gallery, Contact) are accessible to all visitors,
        and the contact form properly saves inquiries.
        """
        for url_name in ['core:home', 'core:about', 'core:gallery', 'core:contact']:
            res = self.client_runner.get(reverse(url_name))
            self.assertEqual(res.status_code, 200)

        # Submit contact inquiry
        post_data = {
            'name': 'Visitor Jane',
            'email': 'jane@external.com',
            'phone': '1234567890',
            'subject': 'Inquiry for Villa Build',
            'message': 'Looking for an estimate on a 4-bedroom villa.',
        }
        res = self.client_runner.post(reverse('core:contact'), data=post_data)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(ContactInquiry.objects.filter(email='jane@external.com').exists())

    def test_admin_can_create_client_via_api(self):
        """
        Site admin can create new clients on the fly via the quick-add API.
        """
        self.client_runner.login(username='admin_boss', password='AdminPassword123!')
        payload = {
            'username': 'client_charlie',
            'first_name': 'Charlie',
            'last_name': 'Brown',
            'email': 'charlie@peanuts.com',
            'phone_number': '555-123-4567',
            'password': 'CharliePassword123!',
        }
        res = self.client_runner.post(
            reverse('projects:api_create_client'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['client']['username'], 'client_charlie')

        # Verify created in DB with is_client=True
        new_client = User.objects.get(username='client_charlie')
        self.assertTrue(new_client.is_client)
        self.assertEqual(new_client.first_name, 'Charlie')

    def test_client_cannot_create_other_clients(self):
        """
        Regular clients cannot access the create client API.
        """
        self.client_runner.login(username='client_alice', password='ClientPassword123!')
        res = self.client_runner.post(
            reverse('projects:api_create_client'),
            data=json.dumps({'username': 'hacker_client'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)


