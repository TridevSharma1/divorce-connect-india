from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from accounts.models import BaseUser

phone_regex = RegexValidator(
    regex=r'^(\+91|0)?[6-9]\d{9}$',
    message="Phone number must be in Indian format (10 digits starting with 6-9, or +91..."
)


class Gender(models.TextChoices):
    """Gender choices for all user profiles."""
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


class VerificationStatus(models.TextChoices):
    """Status choices for lawyer verification requests."""
    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class LawyerVerificationRequest(models.Model):
    """
    Tracks lawyer verification requests submitted for admin review.
    Admin can approve or reject based on submitted documents and information.
    """

    lawyer = models.OneToOneField(
        'lawyers.LawyerProfile',
        on_delete=models.CASCADE,
        related_name='verification_request',
        help_text="Lawyer requesting verification"
    )

    status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        help_text="Current verification status"
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When verification request was submitted"
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When admin reviewed the request"
    )

    reviewed_by = models.ForeignKey(
        BaseUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_lawyer_verifications',
        help_text="Admin who reviewed this request"
    )

    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for rejection if rejected"
    )

    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Admin notes during review"
    )

    class Meta:
        verbose_name = "Lawyer Verification Request"
        verbose_name_plural = "Lawyer Verification Requests"
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.lawyer.full_name} - {self.get_status_display()}"


class TrustReport(models.Model):
    """Trust and safety reports filed by clients or lawyers."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('WARNED', 'Warned'),
        ('BANNED', 'Banned'),
    ]

    reporter = models.ForeignKey(
        BaseUser,
        on_delete=models.CASCADE,
        related_name='submitted_reports',
        help_text='User who submitted this report'
    )
    reported_client = models.ForeignKey(
        'clients.ClientProfile',
        on_delete=models.CASCADE,
        related_name='received_reports',
        null=True,
        blank=True,
        help_text='Client being reported, if applicable'
    )
    reported_lawyer = models.ForeignKey(
        'lawyers.LawyerProfile',
        on_delete=models.CASCADE,
        related_name='received_reports',
        null=True,
        blank=True,
        help_text='Lawyer being reported, if applicable'
    )
    reason = models.CharField(
        max_length=140,
        help_text='Primary reason for filing the report'
    )
    description = models.TextField(
        help_text='Detailed explanation of the incident leading to this report'
    )
    evidence = models.FileField(
        upload_to='report_evidence/',
        blank=True,
        null=True,
        help_text='Optional evidence file supporting the report'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text='Admin review status for this report'
    )
    admin_notes = models.TextField(
        blank=True,
        null=True,
        help_text='Notes entered by the admin during review'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the report was reviewed by an admin'
    )
    reviewed_by = models.ForeignKey(
        BaseUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_trust_reports',
        help_text='Admin who reviewed this report'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trust Report'
        verbose_name_plural = 'Trust Reports'
        ordering = ['-created_at']

    def __str__(self):
        target = self.reported_client or self.reported_lawyer
        return f"Report #{self.id} against {target} - {self.get_status_display()}"

    @property
    def target_name(self):
        if self.reported_client:
            return self.reported_client.get_full_name()
        if self.reported_lawyer:
            return self.reported_lawyer.full_name
        return 'Unknown'


class AdminPanelProfile(models.Model):
    """
    Admin panel user profile linked to BaseUser via OneToOneField.
    Extends authentication capabilities with admin-specific information.
    Only superuser admins can create and manage these profiles.
    """

    # Link to BaseUser (one-to-one relationship)
    user = models.OneToOneField(
        BaseUser,
        on_delete=models.CASCADE,
        related_name='admin_profile',
        help_text="Associated BaseUser account"
    )

    # Personal Information
    full_name = models.CharField(
        max_length=100,
        help_text="Admin's full name"
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.OTHER,
        help_text="Admin's gender"
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Admin's date of birth"
    )

    # Contact Information
    mobile_number = models.CharField(
        max_length=13,
        validators=[phone_regex],
        blank=True,
        help_text="Admin's primary mobile number (10 digits)"
    )

    alternate_mobile_number = models.CharField(
        max_length=13,
        validators=[phone_regex],
        blank=True,
        null=True,
        help_text="Admin's alternate mobile number (optional)"
    )

    # Profile Picture
    profile_picture = models.ImageField(
        upload_to='admin_pictures/',
        null=True,
        blank=True,
        help_text="Admin's profile picture"
    )

    # Profile Completion & Verification Status
    is_profile_complete = models.BooleanField(
        default=False,
        help_text="Has admin completed their profile and submitted for verification?"
    )

    # Verification and Activation
    is_verified_by_superuser = models.BooleanField(
        default=False,
        help_text="Only a superuser admin can toggle this to activate the admin staff account"
    )

    # Timestamps
    date_of_join = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when admin account was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag for an admin panel user profile"
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the admin profile was soft deleted"
    )

    class Meta:
        verbose_name = "Admin Panel Profile"
        verbose_name_plural = "Admin Panel Profiles"
        ordering = ['-date_of_join']

    def __str__(self):
        return f"{self.full_name} ({self.user.email})"

    def save(self, *args, **kwargs):
        """
        Override save to ensure staff status is synced with is_verified_by_superuser.
        Admin users must remain active so they can log in, complete profile details,
        and wait for superuser verification.
        """
        is_new = self.pk is None
        old_verified = False
        if not is_new:
            try:
                old_verified = AdminPanelProfile.objects.get(pk=self.pk).is_verified_by_superuser
            except Exception:
                pass

        self.user.is_staff = self.is_verified_by_superuser
        self.user.save(update_fields=['is_staff'])
        super().save(*args, **kwargs)

        if self.is_verified_by_superuser and not old_verified:
            try:
                from accounts.models import Notification
                import requests
                # 1. Create DB notification
                Notification.objects.create(
                    user=self.user,
                    title="Profile Verified",
                    message="Your admin profile has been verified and activated by superuser.",
                    url="/admin_dashboard/"
                )
                # 2. Trigger real-time toast via FastAPI Websocket helper
                requests.post(
                    "http://127.0.0.1:8000/api/notifications/send-direct",
                    json={
                        "user_id": self.user.id,
                        "title": "Profile Verified",
                        "message": "Your admin profile has been verified and activated by superuser.",
                        "url": "/admin_dashboard/"
                    },
                    timeout=2
                )
            except Exception as e:
                print("Failed to send FastAPI notification:", e)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.user.is_active = False
        self.user.is_staff = False
        self.user.save(update_fields=['is_active', 'is_staff'])
        self.save(update_fields=['is_deleted', 'deleted_at'])


class DeletedAdminPanelProfile(AdminPanelProfile):
    class Meta:
        proxy = True
        verbose_name = 'Deleted Admin Panel Profile'
        verbose_name_plural = 'Deleted Admin Panel Profiles'


class AdminPanelProfileUpdateRequest(models.Model):
    """Holds pending admin profile edits waiting for superuser approval."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    admin_profile = models.ForeignKey(
        AdminPanelProfile,
        on_delete=models.CASCADE,
        related_name='update_requests',
        help_text='Admin profile requesting an update.'
    )

    full_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    mobile_number = models.CharField(
        max_length=13,
        validators=[phone_regex],
        blank=True,
        null=True,
        help_text='Admin primary mobile number for pending updates.'
    )
    alternate_mobile_number = models.CharField(
        max_length=13,
        validators=[phone_regex],
        blank=True,
        null=True,
        help_text='Admin alternate mobile number for pending updates.'
    )
    profile_picture = models.ImageField(
        upload_to='admin_update_requests/',
        null=True,
        blank=True,
        help_text='Updated profile picture submitted for approval.'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text='Current review status for this update request.'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        BaseUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_admin_profile_updates',
        help_text='Superuser who reviewed this update request.'
    )
    admin_notes = models.TextField(
        blank=True,
        null=True,
        help_text='Notes for the superuser review, especially rejection reason.'
    )

    class Meta:
        verbose_name = 'Admin Profile Update Request'
        verbose_name_plural = 'Admin Profile Update Requests'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Update request for {self.admin_profile.full_name} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = 'PENDING'
        if not is_new:
            try:
                old_status = AdminPanelProfileUpdateRequest.objects.get(pk=self.pk).status
            except Exception:
                pass
        
        super().save(*args, **kwargs)

        if not is_new and old_status == 'PENDING' and self.status in ['APPROVED', 'REJECTED']:
            try:
                from accounts.models import Notification
                import requests
                
                title = "Profile Update Approved" if self.status == 'APPROVED' else "Profile Update Rejected"
                message = (
                    "Your admin profile update request was approved by superuser."
                    if self.status == 'APPROVED'
                    else f"Your admin profile update request was rejected by superuser. Notes: {self.admin_notes or 'No notes provided'}"
                )
                
                # 1. Create DB notification
                Notification.objects.create(
                    user=self.admin_profile.user,
                    title=title,
                    message=message,
                    url="/admin_dashboard/"
                )
                
                # 2. Trigger real-time toast via FastAPI Websocket helper
                requests.post(
                    "http://127.0.0.1:8000/api/notifications/send-direct",
                    json={
                        "user_id": self.admin_profile.user.id,
                        "title": title,
                        "message": message,
                        "url": "/admin_dashboard/"
                    },
                    timeout=2
                )
            except Exception as e:
                print("Failed to send FastAPI notification:", e)
