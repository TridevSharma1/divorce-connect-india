import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import BaseUser
from clients.models import ClientProfile
from lawyers.models import LawyerProfile
from adminpanel.models import AdminPanelProfile

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Hard delete accounts (BaseUser and all associated profiles/data) that were soft deleted more than 14 days ago.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=14)
        deleted_count = 0

        # Find users who are soft-deleted:
        # A user is soft-deleted if they are inactive (is_active=False) AND one of their profiles has is_deleted=True and deleted_at <= cutoff.
        # We can look up the profiles directly:
        
        # 1. Clients
        expired_clients = ClientProfile.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        for profile in expired_clients:
            user = profile.user
            self.stdout.write(self.style.WARNING(f"Purging soft-deleted Client account: {user.email} (Soft deleted at: {profile.deleted_at})"))
            user.delete() # CASCADE will delete the profile and related objects
            deleted_count += 1

        # 2. Lawyers
        expired_lawyers = LawyerProfile.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        for profile in expired_lawyers:
            user = profile.user
            self.stdout.write(self.style.WARNING(f"Purging soft-deleted Lawyer account: {user.email} (Soft deleted at: {profile.deleted_at})"))
            user.delete()
            deleted_count += 1

        # 3. Admins
        expired_admins = AdminPanelProfile.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        for profile in expired_admins:
            user = profile.user
            self.stdout.write(self.style.WARNING(f"Purging soft-deleted Admin account: {user.email} (Soft deleted at: {profile.deleted_at})"))
            user.delete()
            deleted_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully purged {deleted_count} soft-deleted account(s) older than 14 days."))
