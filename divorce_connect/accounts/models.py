from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class BaseUserManager(BaseUserManager):
    """Custom manager for BaseUser model with email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with email instead of username."""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with email instead of username."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class BaseUser(AbstractUser):
    """
    Custom user model using email as the unique identifier instead of username.
    This is the single AUTH_USER_MODEL for the entire application.

    All user types (Client, Lawyer, Admin) will be associated with this model
    through OneToOneField relationships with their respective Profile models.
    """

    email = models.EmailField(
        unique=True,
        max_length=254,
        help_text="Email address used for authentication"
    )

    # Override username to be non-unique since we're using email for login
    username = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        unique=False,
        help_text="Username field (optional, not used for authentication)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BaseUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is already required by the model

    class Meta:
        verbose_name = "Base User"
        verbose_name_plural = "Base Users"
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return the user's full name with proper spacing."""
        return (f"{self.first_name} {self.last_name}").strip()

    def get_short_name(self):
        """Return the user's first name."""
        return self.first_name


class Notification(models.Model):
    """User-visible notification messages for clients, lawyers, and admins."""

    user = models.ForeignKey(
        BaseUser,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User who receives this notification'
    )
    title = models.CharField(max_length=120)
    message = models.TextField()
    url = models.CharField(max_length=255, blank=True, null=True,
                           help_text='Optional URL for the notification action')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.user.email}: {self.title}"
