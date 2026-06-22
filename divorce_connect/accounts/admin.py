from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import BaseUser
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
