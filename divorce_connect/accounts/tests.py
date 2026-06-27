from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Notification

User = get_user_model()

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
