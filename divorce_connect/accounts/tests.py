from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Notification, OTPCode

User = get_user_model()

class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reset.user@example.com",
            password="oldpassword123",
            username="resetuser"
        )

    def test_password_reset_flow_allows_new_password(self):
        response = self.client.post(reverse('forgot_password'), {
            'email': self.user.email,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verify_otp'))
        self.assertEqual(self.client.session['otp_purpose'], 'password_reset')
        self.assertEqual(self.client.session['otp_user_id'], self.user.pk)

        otp_code = OTPCode.objects.filter(user=self.user).latest('created_at')
        response = self.client.post(reverse('verify_otp'), {
            'otp': otp_code.code,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('reset_password'))

        response = self.client.post(reverse('reset_password'), {
            'new_password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!',
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPassword123!'))


class NotificationAPITests(APITestCase):
    def setUp(self):
        # Create two users
        self.user1 = User.objects.create_user(
            email="testuser1@example.com",
            password="testpassword123",
            username="testuser1"
        )
        self.user2 = User.objects.create_user(
            email="testuser2@example.com",
            password="testpassword123",
            username="testuser2"
        )
        
        # Create notifications
        self.notif1 = Notification.objects.create(
            user=self.user1,
            title="User 1 Notification",
            message="This is for user 1"
        )
        self.notif2 = Notification.objects.create(
            user=self.user2,
            title="User 2 Notification",
            message="This is for user 2"
        )

        # Get token for user1
        token_url = reverse('token_obtain_pair')
        response = self.client.post(token_url, {
            'email': self.user1.email,
            'password': 'testpassword123'
        })
        self.token = response.data['access']

    def test_unauthenticated_request_fails(self):
        url = reverse('notification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_get_only_user_notifications(self):
        url = reverse('notification-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return notif1, not notif2
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], "User 1 Notification")

    def test_mark_all_read_action(self):
        url = reverse('notification-mark-all-as-read')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        # Ensure it is currently unread
        self.assertFalse(self.notif1.is_read)
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify db status updated
        self.notif1.refresh_from_db()
        self.assertTrue(self.notif1.is_read)


class RegistrationFlowTests(TestCase):
    def test_registration_flow_prevents_db_creation_until_otp_verified(self):
        # 1. Post to registration view
        response = self.client.post(reverse('register'), {
            'role': 'client',
            'first_name': 'Test',
            'last_name': 'Client',
            'email': 'new.client@example.com',
            'password1': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
        })
        
        # Should redirect to verify register OTP page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verify_register_otp'))
        
        # Assert user is NOT in database yet
        self.assertFalse(User.objects.filter(email='new.client@example.com').exists())
        
        # Verify session stores the generated OTP code and purpose
        session = self.client.session
        self.assertEqual(session['otp_purpose'], 'register')
        self.assertEqual(session['reg_email'], 'new.client@example.com')
        otp_code = session['reg_otp']
        self.assertTrue(otp_code)
        
        # 2. Post correct OTP to verify_register_otp
        response = self.client.post(reverse('verify_register_otp'), {
            'otp': otp_code,
        })
        
        # Should redirect to dashboard (or welcome)
        self.assertEqual(response.status_code, 302)
        
        # Assert user is now successfully created in database
        self.assertTrue(User.objects.filter(email='new.client@example.com').exists())
        
        user = User.objects.get(email='new.client@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'Client')
        
        # Verify client profile is also created
        self.assertTrue(hasattr(user, 'client_profile'))

    def test_registration_flow_with_invalid_otp_fails(self):
        response = self.client.post(reverse('register'), {
            'role': 'lawyer',
            'first_name': 'Test',
            'last_name': 'Lawyer',
            'email': 'new.lawyer@example.com',
            'password1': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
        })
        self.assertEqual(response.status_code, 302)
        
        # Post incorrect OTP
        response = self.client.post(reverse('verify_register_otp'), {
            'otp': '000000', # wrong OTP
        })
        
        # Should render verify page with error message (returns 200 OK)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='new.lawyer@example.com').exists())
