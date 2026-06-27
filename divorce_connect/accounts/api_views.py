from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet for managing notifications via REST API.
    Enforces JWT authentication and limits operations strictly to the user's own notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only query/modify their own notifications
        return Notification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically assign the logged-in user when creating a notification via API
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_as_read(self, request):
        """Custom action to mark all unread notifications for the user as read."""
        unread_notifications = self.get_queryset().filter(is_read=False)
        count = unread_notifications.update(is_read=True)
        return Response(
            {"message": f"Successfully marked {count} notification(s) as read."},
            status=status.HTTP_200_OK
        )
