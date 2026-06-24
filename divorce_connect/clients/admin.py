from django.contrib import admin
from .models import ClientProfile, DeletedClientProfile


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
			'fields': ('date_of_join', 'updated_at', 'deleted_at'),
			'classes': ('collapse',),
		}),
	)

	readonly_fields = ('date_of_join', 'updated_at', 'deleted_at')

	list_display = (
		'get_full_name',
		'get_email',
		'mobile_number',
		'gender',
		'marital_status',
		'is_deleted',
		'deleted_at',
		'date_of_join'
	)

	list_filter = ('gender', 'marital_status', 'date_of_join', 'is_deleted')
	search_fields = ('first_name', 'last_name', 'user__email', 'mobile_number')
	ordering = ('-date_of_join',)
	actions = ['soft_delete_clients', 'restore_client_profiles']

	def get_full_name(self, obj):
		return obj.get_full_name()
	get_full_name.short_description = 'Full Name'

	def get_email(self, obj):
		return obj.user.email
	get_email.short_description = 'Email'

	def soft_delete_clients(self, request, queryset):
		count = 0
		for profile in queryset:
			profile.soft_delete()
			count += 1
		self.message_user(request, f'{count} client profile(s) soft deleted.')
	soft_delete_clients.short_description = 'Soft delete selected client profiles'

	def restore_client_profiles(self, request, queryset):
		count = 0
		for profile in queryset:
			profile.is_deleted = False
			profile.deleted_at = None
			profile.user.is_active = True
			profile.user.save(update_fields=['is_active'])
			profile.save(update_fields=['is_deleted', 'deleted_at'])
			count += 1
		self.message_user(request, f'{count} client profile(s) restored.')
	restore_client_profiles.short_description = 'Restore selected client profiles'


@admin.register(DeletedClientProfile)
class DeletedClientProfileAdmin(ClientProfileAdmin):
	"""Admin view for soft deleted client profiles."""

	def get_queryset(self, request):
		return super().get_queryset(request).filter(is_deleted=True)

	actions = ['restore_client_profiles']
	list_display = (
		'get_full_name',
		'get_email',
		'mobile_number',
		'gender',
		'marital_status',
		'deleted_at',
		'date_of_join'
	)

	list_filter = ('gender', 'marital_status', 'date_of_join')
