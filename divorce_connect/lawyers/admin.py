from django.contrib import admin
from .models import LawyerProfile, LawyerProfileUpdateRequest


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
		('Professional Profile & Fees', {
			'fields': (
				'bio',
				'consultation_fee',
				'office_city',
				'profile_picture'
			),
			'description': 'Professional details, consultation rates, and profile media.'
		}),
		('Rating & Verification', {
			'fields': ('rating', 'verified', 'is_profile_complete'),
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
		'consultation_fee',
		'years_of_experience',
		'rating',
		'verified',
		'date_joined'
	)

	list_filter = ('specialization', 'verified', 'rating', 'date_joined', 'years_of_experience', 'is_profile_complete')
	search_fields = ('full_name', 'user__email', 'bar_registration_number', 'state_bar_council', 'office_city')
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


@admin.register(LawyerProfileUpdateRequest)
class LawyerProfileUpdateRequestAdmin(admin.ModelAdmin):
	"""
	Django admin configuration for LawyerProfileUpdateRequest model.
	Allows admins to review and approve/reject profile update requests from lawyers.
	"""

	fieldsets = (
		('Request Information', {
			'fields': ('lawyer', 'status', 'submitted_at', 'reviewed_at'),
			'description': 'Lawyer profile update request details.'
		}),
		('Personal Information Updates', {
			'fields': ('full_name', 'gender', 'date_of_birth'),
		}),
		('Professional Information Updates', {
			'fields': (
				'years_of_experience',
				'specialization',
			),
		}),
		('Professional Profile & Fees Updates', {
			'fields': (
				'bio',
				'consultation_fee',
				'office_city',
				'profile_picture'
			),
		}),
		('Contact Information Updates', {
			'fields': ('mobile_number', 'alternate_mobile_number'),
		}),
		('Admin Review', {
			'fields': ('admin_notes',),
			'description': 'Add notes for rejection reasons or approval comments.'
		}),
	)

	readonly_fields = ('lawyer', 'submitted_at', 'reviewed_at')

	list_display = (
		'get_lawyer_name',
		'status',
		'submitted_at',
		'reviewed_at',
		'get_consultation_fee_update',
	)

	list_filter = ('status', 'submitted_at', 'reviewed_at')
	search_fields = ('lawyer__full_name', 'lawyer__user__email')
	ordering = ('-submitted_at',)
	actions = ['approve_requests', 'reject_requests']

	def get_lawyer_name(self, obj):
		return obj.lawyer.full_name
	get_lawyer_name.short_description = 'Lawyer'

	def get_consultation_fee_update(self, obj):
		return f"₹{obj.consultation_fee}" if obj.consultation_fee else "Not Updated"
	get_consultation_fee_update.short_description = 'Fee Update'

	def approve_requests(self, request, queryset):
		from django.utils import timezone
		count = queryset.update(status='APPROVED', reviewed_at=timezone.now())
		self.message_user(request, f'{count} update request(s) approved.')
	approve_requests.short_description = 'Approve selected requests'

	def reject_requests(self, request, queryset):
		count = 0
		for obj in queryset:
			if obj.admin_notes:  # Only reject if admin notes provided
				obj.status = 'REJECTED'
				obj.reviewed_at = timezone.now()
				obj.save()
				count += 1
		if count > 0:
			self.message_user(request, f'{count} update request(s) rejected.')
		else:
			self.message_user(request, 'Please add admin notes before rejecting.', level='warning')
	reject_requests.short_description = 'Reject selected requests (requires admin notes)'
