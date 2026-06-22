from django.db import models
from django.core.validators import RegexValidator
from accounts.models import BaseUser


class Gender(models.TextChoices):
    """Gender choices for all user profiles."""
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


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
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )

    mobile_number = models.CharField(
        max_length=17,
        validators=[phone_regex],
        help_text="Admin's primary mobile number"
    )

    alternate_mobile_number = models.CharField(
        max_length=17,
        validators=[phone_regex],
        blank=True,
        null=True,
        help_text="Admin's alternate mobile number (optional)"
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
