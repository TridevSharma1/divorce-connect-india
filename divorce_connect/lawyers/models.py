from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from accounts.models import BaseUser


class Specialization(models.TextChoices):
    """Legal specialization choices for lawyers."""
    CRIMINAL = "criminal", "Criminal Law"
    FAMILY = "family", "Family Law"
    CORPORATE = "corporate", "Corporate Law"
    INTELLECTUAL_PROPERTY = "ip", "Intellectual Property"
    LABOR = "labor", "Labor Law"
    TAX = "tax", "Tax Law"
    REAL_ESTATE = "real_estate", "Real Estate"
    BANKRUPTCY = "bankruptcy", "Bankruptcy Law"
    OTHER = "other", "Other"


class Gender(models.TextChoices):
    """Gender choices for all user profiles."""
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


class LawyerProfile(models.Model):
    """
    Lawyer user profile linked to BaseUser via OneToOneField.
    Extends authentication capabilities with lawyer-specific professional information.
    """

    # Link to BaseUser (one-to-one relationship)
    user = models.OneToOneField(
        BaseUser,
        on_delete=models.CASCADE,
        related_name='lawyer_profile',
        help_text="Associated BaseUser account"
    )

    # Personal Information
    full_name = models.CharField(
        max_length=100,
        help_text="Lawyer's full name"
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.OTHER,
        help_text="Lawyer's gender"
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Lawyer's date of birth"
    )

    # Professional Information
    bar_registration_number = models.CharField(
        max_length=50,
        unique=True,
        blank=False,
        help_text="Bar council registration/license number - Must be entered by user"
    )

    state_bar_council = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the state bar council where registered"
    )

    years_of_experience = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        default=0,
        help_text="Number of years of legal practice experience"
    )

    specialization = models.CharField(
        max_length=50,
        choices=Specialization.choices,
        default=Specialization.OTHER,
        help_text="Primary area of legal specialization"
    )

    # Ratings and Verification
    rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        help_text="Professional rating (0.0 to 5.0 scale)"
    )

    verified = models.BooleanField(
        default=False,
        help_text="Is the lawyer's credentials verified by admin?"
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
        help_text="Lawyer's primary mobile number (10 digits)"
    )

    alternate_mobile_number = models.CharField(
        max_length=13,
        validators=[phone_regex],
        blank=True,
        null=True,
        help_text="Lawyer's alternate mobile number (optional)"
    )

    # Profile Picture
    profile_picture = models.ImageField(
        upload_to='lawyer_pictures/',
        null=True,
        blank=True,
        help_text="Lawyer's profile picture"
    )

    # Profile Completion & Verification Status
    is_profile_complete = models.BooleanField(
        default=False,
        help_text="Has lawyer completed their profile and submitted for verification?"
    )

    # Timestamps
    date_joined = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when lawyer joined the platform"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    class Meta:
        verbose_name = "Lawyer Profile"
        verbose_name_plural = "Lawyer Profiles"
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['verified', '-rating']),
            models.Index(fields=['specialization']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.user.email})"
