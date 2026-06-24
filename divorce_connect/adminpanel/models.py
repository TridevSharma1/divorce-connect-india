from django.db import models
from django.core.validators import RegexValidator
from accounts.models import BaseUser


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
    phone_regex = RegexValidator(
        regex=r'^(\+91|0)?[6-9]\d{9}$',
        message="Phone number must be in Indian format (10 digits starting with 6-9, or +91..."
    )

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

    class Meta:
        verbose_name = "Admin Panel Profile"
        verbose_name_plural = "Admin Panel Profiles"
        ordering = ['-date_of_join']

    def __str__(self):
        return f"{self.full_name} ({self.user.email})"

    def save(self, *args, **kwargs):
        """
        Override save to ensure staff and is_active status are synced with is_verified_by_superuser.
        """
        self.user.is_staff = self.is_verified_by_superuser
        self.user.is_active = self.is_verified_by_superuser
        self.user.save(update_fields=['is_staff', 'is_active'])
        super().save(*args, **kwargs)
