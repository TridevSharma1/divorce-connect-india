from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import AdminPanelProfile


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
			'fields': ('date_of_join', 'updated_at'),
			'classes': ('collapse',),
		}),
	)

	readonly_fields = ('date_of_join', 'updated_at')

	list_display = (
		'full_name',
		'get_email',
		'get_verification_status',
		'get_staff_status',
		'date_of_join'
	)

	list_filter = ('is_verified_by_superuser', 'date_of_join')
	search_fields = ('full_name', 'user__email')
	ordering = ('-date_of_join',)
	actions = ['verify_admin_accounts', 'unverify_admin_accounts']

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
