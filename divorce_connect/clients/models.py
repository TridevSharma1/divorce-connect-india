from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from accounts.models import BaseUser


class MaritalStatus(models.TextChoices):
    """Marital status choices for clients."""
    SINGLE = "single", "Single"
    MARRIED = "married", "Married"
    DIVORCED = "divorced", "Divorced"
    WIDOWED = "widowed", "Widowed"
    SEPARATED = "separated", "Separated"


class Gender(models.TextChoices):
    """Gender choices for all user profiles."""
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


class ClientProfile(models.Model):
    """
    Client user profile linked to BaseUser via OneToOneField.
    Extends authentication capabilities with client-specific information.
    """

    # Link to BaseUser (one-to-one relationship)
    user = models.OneToOneField(
        BaseUser,
        on_delete=models.CASCADE,
        related_name='client_profile',
        help_text="Associated BaseUser account"
    )

    # Personal Information
    first_name = models.CharField(
        max_length=50,
        help_text="Client's first name"
    )

    last_name = models.CharField(
        max_length=50,
        help_text="Client's last name"
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.OTHER,
        help_text="Client's gender"
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Client's date of birth"
    )

    marital_status = models.CharField(
        max_length=20,
        choices=MaritalStatus.choices,
        default=MaritalStatus.SINGLE,
        help_text="Client's current marital status"
    )

    # Contact Information
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )

    mobile_number = models.CharField(
        max_length=17,
        validators=[phone_regex],
        help_text="Client's primary mobile number"
    )

    alternate_mobile_number = models.CharField(
        max_length=17,
        validators=[phone_regex],
        blank=True,
        null=True,
        help_text="Client's alternate mobile number (optional)"
    )

    # Timestamps
    date_of_join = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when client joined the platform"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    class Meta:
        verbose_name = "Client Profile"
        verbose_name_plural = "Client Profiles"
        ordering = ['-date_of_join']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user.email})"

    def get_full_name(self):
        """Return the client's full name."""
        return f"{self.first_name} {self.last_name}".strip()
