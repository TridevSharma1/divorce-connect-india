from django.contrib import admin
from .models import LawyerProfile


@admin.register(LawyerProfile)
class LawyerProfileAdmin(admin.ModelAdmin):
	"""
	Django admin configuration for LawyerProfile model.
	Allows admins to view, manage, and verify lawyer profiles linked to BaseUser accounts.
	"""

	fieldsets = (
		('User Association', {
			'fields': ('user',),
			'description': 'The BaseUser account associated with this lawyer profile.'
		}),
		('Personal Information', {
			'fields': ('full_name', 'gender', 'date_of_birth'),
		}),
		('Professional Information', {
			'fields': (
				'bar_registration_number',
				'state_bar_council',
				'years_of_experience',
				'specialization'
			),
		}),
		('Rating & Verification', {
			'fields': ('rating', 'verified'),
			'description': 'Verification must be done by admin after credential verification.'
		}),
		('Contact Information', {
			'fields': ('mobile_number', 'alternate_mobile_number'),
		}),
		('Metadata', {
			'fields': ('date_joined', 'updated_at'),
			'classes': ('collapse',),
		}),
	)

	readonly_fields = ('date_joined', 'updated_at')

	list_display = (
		'full_name',
		'get_email',
		'specialization',
		'years_of_experience',
		'rating',
		'verified',
		'date_joined'
	)

	list_filter = ('specialization', 'verified', 'rating', 'date_joined', 'years_of_experience')
	search_fields = ('full_name', 'user__email', 'bar_registration_number', 'state_bar_council')
	ordering = ('-date_joined',)
	actions = ['mark_verified', 'mark_unverified']

	def get_email(self, obj):
		return obj.user.email
	get_email.short_description = 'Email'

	def mark_verified(self, request, queryset):
		count = queryset.update(verified=True)
		self.message_user(request, f'{count} lawyer(s) marked as verified.')
	mark_verified.short_description = 'Mark selected lawyers as verified'

	def mark_unverified(self, request, queryset):
		count = queryset.update(verified=False)
		self.message_user(request, f'{count} lawyer(s) marked as unverified.')
	mark_unverified.short_description = 'Mark selected lawyers as unverified'
