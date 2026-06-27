from django.contrib import admin
from .models import (
    LawyerProfile,
    DeletedLawyerProfile,
    CaseRequest,
    CaseDocument,
    CaseDocumentVerification,
    LawyerProfileUpdateRequest,
    LawyerRating,
    CaseMessage,
)


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
			'fields': ('date_joined', 'updated_at', 'deleted_at'),
			'classes': ('collapse',),
		}),
	)

	readonly_fields = ('date_joined', 'updated_at', 'deleted_at')

	list_display = (
		'full_name',
		'get_email',
		'specialization',
		'consultation_fee',
		'years_of_experience',
		'rating',
		'verified',
		'is_deleted',
		'deleted_at',
		'date_joined'
	)

	list_filter = ('specialization', 'verified', 'rating', 'date_joined', 'years_of_experience', 'is_profile_complete', 'is_deleted')
	search_fields = ('full_name', 'user__email', 'bar_registration_number', 'state_bar_council', 'office_city')
	ordering = ('-date_joined',)
	actions = ['mark_verified', 'mark_unverified', 'soft_delete_lawyers', 'restore_lawyers']

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

	def soft_delete_lawyers(self, request, queryset):
		count = 0
		for profile in queryset:
			profile.soft_delete()
			count += 1
		self.message_user(request, f'{count} lawyer profile(s) soft deleted.')
	soft_delete_lawyers.short_description = 'Soft delete selected lawyer profiles'

	def restore_lawyers(self, request, queryset):
		count = 0
		for profile in queryset:
			profile.is_deleted = False
			profile.deleted_at = None
			profile.user.is_active = True
			profile.user.save(update_fields=['is_active'])
			profile.save(update_fields=['is_deleted', 'deleted_at'])
			count += 1
		self.message_user(request, f'{count} lawyer profile(s) restored.')
	restore_lawyers.short_description = 'Restore selected lawyer profiles'


@admin.register(DeletedLawyerProfile)
class DeletedLawyerProfileAdmin(LawyerProfileAdmin):
	"""Admin view for soft deleted lawyer profiles."""

	def get_queryset(self, request):
		return super().get_queryset(request).filter(is_deleted=True)

	actions = ['restore_lawyers']
	list_display = (
		'full_name',
		'get_email',
		'specialization',
		'consultation_fee',
		'years_of_experience',
		'rating',
		'verified',
		'deleted_at',
		'date_joined'
	)

	list_filter = ('specialization', 'verified', 'rating', 'date_joined', 'years_of_experience', 'is_profile_complete')


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
		count = 0
		for obj in queryset:
			if obj.status != 'APPROVED':
				lawyer = obj.lawyer
				lawyer.full_name = obj.full_name or lawyer.full_name
				lawyer.gender = obj.gender or lawyer.gender
				lawyer.date_of_birth = obj.date_of_birth or lawyer.date_of_birth
				lawyer.years_of_experience = obj.years_of_experience if obj.years_of_experience is not None else lawyer.years_of_experience
				lawyer.specialization = obj.specialization or lawyer.specialization
				lawyer.bio = obj.bio or lawyer.bio
				lawyer.consultation_fee = obj.consultation_fee if obj.consultation_fee is not None else lawyer.consultation_fee
				lawyer.office_city = obj.office_city or lawyer.office_city
				lawyer.mobile_number = obj.mobile_number or lawyer.mobile_number
				lawyer.alternate_mobile_number = obj.alternate_mobile_number or lawyer.alternate_mobile_number
				if obj.profile_picture:
					lawyer.profile_picture = obj.profile_picture
				lawyer.save()
				obj.status = 'APPROVED'
				obj.reviewed_at = timezone.now()
				obj.save()
				count += 1
		self.message_user(request, f'{count} update request(s) approved.')
	approve_requests.short_description = 'Approve selected requests'


@admin.register(CaseRequest)
class CaseRequestAdmin(admin.ModelAdmin):
    """Admin interface for case requests."""

    list_display = (
        'id',
        'client',
        'lawyer',
        'status',
        'workflow_stage',
        'created_at',
        'updated_at',
    )
    list_filter = ('status', 'workflow_stage', 'created_at', 'updated_at')
    search_fields = ('client__user__email', 'lawyer__user__email', 'message', 'response_message')
    ordering = ('-created_at',)


@admin.register(CaseDocument)
class CaseDocumentAdmin(admin.ModelAdmin):
    """Admin interface for case documents."""

    list_display = (
        'id',
        'case_request',
        'document_type',
        'uploaded_at',
    )
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('case_request__client__user__email', 'case_request__lawyer__user__email')
    ordering = ('-uploaded_at',)


@admin.register(CaseDocumentVerification)
class CaseDocumentVerificationAdmin(admin.ModelAdmin):
    """Admin interface for case document verifications."""

    list_display = (
        'id',
        'document',
        'status',
        'verified_by',
        'verified_at',
    )
    list_filter = ('status', 'verified_at')
    search_fields = ('document__case_request__client__user__email', 'document__case_request__lawyer__user__email')
    ordering = ('-verified_at',)


@admin.register(LawyerRating)
class LawyerRatingAdmin(admin.ModelAdmin):
    """Admin interface for lawyer ratings and reviews."""

    list_display = (
        'id',
        'lawyer',
        'client',
        'score',
        'created_at',
    )
    list_filter = ('score', 'created_at')
    search_fields = ('lawyer__full_name', 'lawyer__user__email', 'client__user__email', 'review_text')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)


@admin.register(CaseMessage)
class CaseMessageAdmin(admin.ModelAdmin):
    """Admin interface for case chat messages."""

    list_display = (
        'id',
        'case',
        'sender_type',
        'sender_user',
        'is_read',
        'created_at',
    )
    list_filter = ('sender_type', 'is_read', 'created_at')
    search_fields = ('case__client__user__email', 'case__lawyer__user__email', 'sender_user__email', 'text')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)