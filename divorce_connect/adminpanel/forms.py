from django import forms
from django.contrib.auth.models import User
from accounts.models import BaseUser
from accounts.forms import BaseUserCreationForm
from .models import AdminPanelProfile, Gender


class AdminPanelRegistrationForm(BaseUserCreationForm):
	"""
	Extended registration form for Admin Panel users.
	Combines BaseUser creation with AdminPanelProfile creation in a single form.

	NOTE: Only a superuser admin should be able to create admin accounts.
	This form should be used in admin-only views/pages with permission checks.
	"""

	# Personal Information
	full_name = forms.CharField(
		max_length=100,
		label="Full Name",
		widget=forms.TextInput(attrs={
			'class': 'form-control',
			'placeholder': 'Enter full name'
		})
	)

	gender = forms.ChoiceField(
		choices=Gender.choices,
		label="Gender",
		widget=forms.Select(attrs={'class': 'form-control'})
	)

	date_of_birth = forms.DateField(
		required=False,
		label="Date of Birth",
		widget=forms.DateInput(attrs={
			'class': 'form-control',
			'type': 'date'
		})
	)

	# Contact Information
	mobile_number = forms.CharField(
		max_length=17,
		label="Mobile Number",
		widget=forms.TextInput(attrs={
			'class': 'form-control',
			'placeholder': '+1234567890'
		})
	)

	alternate_mobile_number = forms.CharField(
		max_length=17,
		required=False,
		label="Alternate Mobile Number (Optional)",
		widget=forms.TextInput(attrs={
			'class': 'form-control',
			'placeholder': '+1234567890'
		})
	)

	class Meta(BaseUserCreationForm.Meta):
		model = BaseUser
		fields = (
			'email',
			'full_name',
			'gender',
			'date_of_birth',
			'mobile_number',
			'alternate_mobile_number',
			'password1',
			'password2'
		)

	def save(self, commit=True):
		"""
		Save BaseUser instance and create associated AdminPanelProfile.
		By default, is_verified_by_superuser is False until a superuser explicitly activates it.
		"""
		user = super().save(commit=commit)

		if commit:
			AdminPanelProfile.objects.create(
				user=user,
				full_name=self.cleaned_data.get('full_name'),
				gender=self.cleaned_data.get('gender'),
				date_of_birth=self.cleaned_data.get('date_of_birth'),
				mobile_number=self.cleaned_data.get('mobile_number'),
				alternate_mobile_number=self.cleaned_data.get('alternate_mobile_number'),
				is_verified_by_superuser=False,  # Must be verified by superuser
			)

		return user


class AdminPanelProfileUpdateForm(forms.ModelForm):
	"""
	Form for updating an existing AdminPanelProfile.
	Email cannot be changed after registration.
	"""

	email = forms.EmailField(
		label="Email Address",
		disabled=True,
		help_text="Email cannot be changed after registration"
	)

	class Meta:
		model = AdminPanelProfile
		fields = (
			'full_name',
			'gender',
			'date_of_birth',
			'mobile_number',
			'alternate_mobile_number'
		)
		widgets = {
			'full_name': forms.TextInput(attrs={'class': 'form-control'}),
			'gender': forms.Select(attrs={'class': 'form-control'}),
			'date_of_birth': forms.DateInput(attrs={
				'class': 'form-control',
				'type': 'date'
			}),
			'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
			'alternate_mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance and self.instance.user:
			self.fields['email'].initial = self.instance.user.email


class AdminVerificationForm(forms.ModelForm):
	"""
	Form for superusers to verify and activate admin staff accounts.
	Only the is_verified_by_superuser field can be modified.
	"""

	class Meta:
		model = AdminPanelProfile
		fields = ('is_verified_by_superuser',)
		widgets = {
			'is_verified_by_superuser': forms.CheckboxInput(attrs={
				'class': 'form-check-input'
			}),
		}
		labels = {
			'is_verified_by_superuser': 'Verify and Activate Admin Account',
		}
		help_texts = {
			'is_verified_by_superuser': 'Check to activate this admin staff account',
		}
