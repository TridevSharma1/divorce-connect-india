from django.contrib import admin
from .models import ClientProfile


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
	"""
	Django admin configuration for ClientProfile model.
	Allows admins to view and manage client profiles linked to BaseUser accounts.
	"""

	fieldsets = (
		('User Association', {
			'fields': ('user',),
			'description': 'The BaseUser account associated with this client profile.'
		}),
		('Personal Information', {
			'fields': ('first_name', 'last_name', 'gender', 'date_of_birth', 'marital_status'),
		}),
		('Contact Information', {
			'fields': ('mobile_number', 'alternate_mobile_number'),
		}),
		('Metadata', {
			'fields': ('date_of_join', 'updated_at'),
			'classes': ('collapse',),
		}),
	)

	readonly_fields = ('date_of_join', 'updated_at')

	list_display = (
		'get_full_name',
		'get_email',
		'mobile_number',
		'gender',
		'marital_status',
		'date_of_join'
	)

	list_filter = ('gender', 'marital_status', 'date_of_join')
	search_fields = ('first_name', 'last_name', 'user__email', 'mobile_number')
	ordering = ('-date_of_join',)

	def get_full_name(self, obj):
		return obj.get_full_name()
	get_full_name.short_description = 'Full Name'

	def get_email(self, obj):
		return obj.user.email
	get_email.short_description = 'Email'
