from django.test import TestCase
from django.urls import reverse

from accounts.models import BaseUser
from clients.models import ClientProfile
from lawyers.models import CaseRequest, LawyerProfile


class CaseOrderViewTests(TestCase):
    def setUp(self):
        self.lawyer_user = BaseUser.objects.create_user(
            email='lawyer@example.com',
            password='secret123'
        )
        self.lawyer_profile = LawyerProfile.objects.create(
            user=self.lawyer_user,
            full_name='Test Lawyer',
            bar_registration_number='BAR12345',
            verified=True,
            is_profile_complete=True,
        )

        self.client_user = BaseUser.objects.create_user(
            email='client@example.com',
            password='secret123'
        )
        self.client_profile = ClientProfile.objects.create(
            user=self.client_user,
            first_name='Client',
            last_name='Name',
            mobile_number='9876543210',
            address='123 Test Street',
            pincode='123456',
        )
        self.case_request = CaseRequest.objects.create(
            client=self.client_profile,
            lawyer=self.lawyer_profile,
            message='Need help with a divorce filing.',
        )

    def test_case_order_page_renders_pending_requests_for_verified_lawyer(self):
        self.client.force_login(self.lawyer_user)

        response = self.client.get(reverse('lawyer_case_orders'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Need help with a divorce filing.')
        self.assertContains(response, 'Client Name')
