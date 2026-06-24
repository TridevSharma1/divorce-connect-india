from django.contrib import admin
from django.utils import timezone
from django.utils.safestring import mark_safe
from .models import AdminPanelProfile, DeletedAdminPanelProfile, AdminPanelProfileUpdateRequest


@admin.register(AdminPanelProfile)
class AdminPanelProfileAdmin(admin.ModelAdmin):
	"""
	Django admin configuration for AdminPanelProfile model.
	Only superusers can create and verify admin staff accounts.
	This admin interface manages the verification status of admin accounts.
	"""

	fieldsets = (
		('User Association', {
			'fields': ('user',),
			'description': 'The BaseUser account associated with this admin profile.'
		}),
		('Personal Information', {
			'fields': ('full_name', 'gender', 'date_of_birth'),
		}),
		('Contact Information', {
			'fields': ('mobile_number', 'alternate_mobile_number'),
		}),
		('Verification & Activation', {
			'fields': ('is_verified_by_superuser',),
			'description': 'Only superusers can verify and activate admin staff accounts. '
					 'When checked, this automatically sets is_staff and is_active on the BaseUser.',
		}),
		('Metadata', {
			'fields': ('date_of_join', 'updated_at', 'deleted_at'),
			'classes': ('collapse',),
		}),
	)

	readonly_fields = ('date_of_join', 'updated_at', 'deleted_at')

	list_display = (
		'full_name',
		'get_email',
		'get_verification_status',
		'get_staff_status',
		'is_deleted',
		'deleted_at',
		'date_of_join'
	)

	list_filter = ('is_verified_by_superuser', 'date_of_join', 'is_deleted')
	search_fields = ('full_name', 'user__email')
	ordering = ('-date_of_join',)
	actions = ['verify_admin_accounts', 'unverify_admin_accounts', 'soft_delete_admin_profiles', 'restore_admin_profiles']

	def has_add_permission(self, request):
		"""Only superusers can add new admin profiles."""
		return request.user.is_superuser

	def has_delete_permission(self, request, obj=None):
		"""Only superusers can delete admin profiles."""
		return request.user.is_superuser

	def has_change_permission(self, request, obj=None):
		"""Only superusers can change admin profiles."""
		return request.user.is_superuser

	def get_email(self, obj):
		return obj.user.email
	get_email.short_description = 'Email'

	def get_verification_status(self, obj):
		if obj.is_verified_by_superuser:
			return mark_safe(
				'<span style="color: green; font-weight: bold;">✓ Verified</span>'
			)
		else:
			return mark_safe(
				'<span style="color: red; font-weight: bold;">✗ Unverified</span>'
			)
	get_verification_status.short_description = 'Verification Status'

	def get_staff_status(self, obj):
		if obj.user.is_staff:
			return mark_safe(
				'<span style="color: green; font-weight: bold;">Staff</span>'
			)
		else:
			return mark_safe(
				'<span style="color: gray;">Not Staff</span>'
			)
	get_staff_status.short_description = 'Staff Status'

	def verify_admin_accounts(self, request, queryset):
		count = queryset.update(is_verified_by_superuser=True)
		for obj in queryset:
			obj.save()
		self.message_user(request, f'{count} admin account(s) verified and activated.')
	verify_admin_accounts.short_description = 'Verify and activate selected admin accounts'

	def unverify_admin_accounts(self, request, queryset):
		count = queryset.update(is_verified_by_superuser=False)
		for obj in queryset:
			obj.save()
		self.message_user(request, f'{count} admin account(s) deactivated.')
	unverify_admin_accounts.short_description = 'Deactivate selected admin accounts'

	def soft_delete_admin_profiles(self, request, queryset):
		count = 0
		for profile in queryset:
			profile.soft_delete()
			count += 1
		self.message_user(request, f'{count} admin profile(s) soft deleted.')
	soft_delete_admin_profiles.short_description = 'Soft delete selected admin profiles'

	def restore_admin_profiles(self, request, queryset):
		count = 0
		for profile in queryset:
			profile.is_deleted = False
			profile.deleted_at = None
			profile.user.is_active = True
			profile.save()
			count += 1
		self.message_user(request, f'{count} admin profile(s) restored.')
	restore_admin_profiles.short_description = 'Restore selected admin profiles'


@admin.register(DeletedAdminPanelProfile)
class DeletedAdminPanelProfileAdmin(AdminPanelProfileAdmin):
	"""Admin view for soft deleted admin panel profiles."""

	def get_queryset(self, request):
		return super().get_queryset(request).filter(is_deleted=True)

	actions = ['restore_admin_profiles']
	list_display = (
		'full_name',
		'get_email',
		'get_verification_status',
		'get_staff_status',
		'deleted_at',
		'date_of_join'
	)

	list_filter = ('is_verified_by_superuser', 'date_of_join')


@admin.register(AdminPanelProfileUpdateRequest)
class AdminPanelProfileUpdateRequestAdmin(admin.ModelAdmin):
	"""Superuser admin interface for reviewing admin profile update requests."""

	fieldsets = (
		('Request Information', {
			'fields': ('admin_profile', 'status', 'submitted_at', 'reviewed_at', 'reviewed_by'),
			'description': 'Pending admin profile edit request details.'
		}),
		('Personal Information Updates', {
			'fields': ('full_name', 'gender', 'date_of_birth'),
		}),
		('Contact Information Updates', {
			'fields': ('mobile_number', 'alternate_mobile_number'),
		}),
		('Profile Picture Update', {
			'fields': ('profile_picture',),
		}),
		('Admin Review', {
			'fields': ('admin_notes',),
			'description': 'Add notes for the review, especially a rejection reason.',
		}),
	)

	readonly_fields = ('admin_profile', 'submitted_at', 'reviewed_at', 'reviewed_by')

	list_display = (
		'get_admin_name',
		'status',
		'submitted_at',
		'reviewed_at',
	)

	list_filter = ('status', 'submitted_at', 'reviewed_at')
	search_fields = ('admin_profile__full_name', 'admin_profile__user__email')
	ordering = ('-submitted_at',)
	actions = ['approve_requests', 'reject_requests']

	def get_admin_name(self, obj):
		return obj.admin_profile.full_name
	get_admin_name.short_description = 'Admin'

	def apply_request(self, request_obj):
		profile = request_obj.admin_profile
		if request_obj.full_name:
			profile.full_name = request_obj.full_name
		if request_obj.gender:
			profile.gender = request_obj.gender
		if request_obj.date_of_birth:
			profile.date_of_birth = request_obj.date_of_birth
		if request_obj.mobile_number:
			profile.mobile_number = request_obj.mobile_number
		if request_obj.alternate_mobile_number is not None:
			profile.alternate_mobile_number = request_obj.alternate_mobile_number
		if request_obj.profile_picture:
			profile.profile_picture = request_obj.profile_picture
		profile.is_verified_by_superuser = True
		profile.save()

	def save_model(self, request, obj, form, change):
		if change and obj.status == 'APPROVED':
			obj.reviewed_by = request.user
			obj.reviewed_at = obj.reviewed_at or timezone.now()
			super().save_model(request, obj, form, change)
			self.apply_request(obj)
			return

		if change and obj.status == 'REJECTED':
			obj.reviewed_by = request.user
			obj.reviewed_at = obj.reviewed_at or timezone.now()
			super().save_model(request, obj, form, change)
			return

		super().save_model(request, obj, form, change)

	def approve_requests(self, request, queryset):
		count = 0
		for obj in queryset:
			obj.status = 'APPROVED'
			obj.reviewed_by = request.user
			obj.reviewed_at = timezone.now()
			obj.save()
			self.apply_request(obj)
			count += 1
		self.message_user(request, f'{count} update request(s) approved.')
	approve_requests.short_description = 'Approve selected requests'

	def reject_requests(self, request, queryset):
		count = 0
		for obj in queryset:
			obj.status = 'REJECTED'
			obj.reviewed_by = request.user
			obj.reviewed_at = timezone.now()
			obj.save()
			count += 1
		self.message_user(request, f'{count} update request(s) rejected.')
	reject_requests.short_description = 'Reject selected requests'
