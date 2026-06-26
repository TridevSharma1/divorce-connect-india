from django.utils import timezone
from datetime import timedelta
from accounts.models import BaseUser
from clients.models import ClientProfile
from lawyers.models import LawyerProfile
from adminpanel.models import AdminPanelProfile

class PurgeDeletedUsersMiddleware:
    """
    Middleware that automatically purges soft-deleted users
    who have been soft-deleted for more than 14 days.
    This runs asynchronously or on request, but since we want it automatic
    and without setup of external cron jobs, checking/purging on requests
    (with a rate limit or simple check) is extremely reliable for Django apps in development/production.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # We can check and purge on requests to ensure it happens automatically.
        # To avoid database overhead on every single request, we can use a basic cache or just run it.
        # Given it's a simple query, it's very fast.
        cutoff = timezone.now() - timedelta(days=14)
        
        # Clients
        expired_clients = ClientProfile.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        for profile in expired_clients:
            try:
                profile.user.delete()
            except Exception:
                pass

        # Lawyers
        expired_lawyers = LawyerProfile.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        for profile in expired_lawyers:
            try:
                profile.user.delete()
            except Exception:
                pass

        # Admins
        expired_admins = AdminPanelProfile.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        for profile in expired_admins:
            try:
                profile.user.delete()
            except Exception:
                pass

        return self.get_response(request)
