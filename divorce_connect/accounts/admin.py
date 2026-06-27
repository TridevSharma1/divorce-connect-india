from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import BaseUser, Notification, OTPCode, DeleteAccountToken
from .forms import BaseUserCreationForm, BaseUserChangeForm


@admin.register(BaseUser)
class BaseUserAdmin(BaseUserAdmin):
	"""
	Custom Django admin configuration for BaseUser model.
	Uses email as the primary identifier for authentication.
	"""

	form = BaseUserChangeForm
	add_form = BaseUserCreationForm

	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Personal Info', {'fields': ('first_name', 'last_name')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
		('Important Dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
	)

	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'password1', 'password2'),
		}),
	)

	list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'created_at')
	list_filter = ('is_staff', 'is_active', 'is_superuser', 'created_at')
	search_fields = ('email', 'first_name', 'last_name')
	ordering = ('-created_at',)
	readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for user notifications."""

    list_display = ('user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__email', 'title', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    """Admin configuration for OTP codes."""

    list_display = ('user', 'code', 'created_at', 'is_used', 'is_expired')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__email', 'code')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.short_description = 'Expired'
    is_expired.boolean = True


@admin.register(DeleteAccountToken)
class DeleteAccountTokenAdmin(admin.ModelAdmin):
    """Admin configuration for account deletion tokens."""

    list_display = ('user', 'token', 'created_at', 'is_used', 'is_expired')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__email', 'token')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'token')

    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.short_description = 'Expired'
    is_expired.boolean = True