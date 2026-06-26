from django import forms
from accounts.models import BaseUser
from accounts.forms import BaseUserCreationForm
from .models import ClientProfile, MaritalStatus, Gender
from core_utils import validate_profile_picture


class ClientRegistrationForm(BaseUserCreationForm):
    """
    Extended registration form for Client users.
    Combines BaseUser creation with ClientProfile creation in a single form.
    """

    # Personal Information
    first_name = forms.CharField(
        max_length=50,
        required=True,
        label="First Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )

    last_name = forms.CharField(
        max_length=50,
        required=True,
        label="Last Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
        })
    )

    gender = forms.ChoiceField(
        required=True,
        choices=Gender.choices,
        label="Gender",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_of_birth = forms.DateField(
        required=True,
        label="Date of Birth",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    marital_status = forms.ChoiceField(
        required=True,
        choices=MaritalStatus.choices,
        label="Marital Status",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # Contact Information
    mobile_number = forms.CharField(
        max_length=13,
        required=True,
        label="Mobile Number",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '9876543210 or +919876543210'
        })
    )

    alternate_mobile_number = forms.CharField(
        max_length=13,
        required=False,
        label="Alternate Mobile Number (Optional)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '9876543210 or +919876543210'
        })
    )

    class Meta(BaseUserCreationForm.Meta):
        model = BaseUser
        fields = (
            'email',
            'first_name',
            'last_name',
            'gender',
            'date_of_birth',
            'marital_status',
            'mobile_number',
            'alternate_mobile_number',
            'password1',
            'password2'
        )

    def save(self, commit=True):
        """
        Save BaseUser instance and create associated ClientProfile.
        """
        user = super().save(commit=commit)

        if commit:
            ClientProfile.objects.create(
                user=user,
                first_name=self.cleaned_data.get('first_name'),
                last_name=self.cleaned_data.get('last_name'),
                gender=self.cleaned_data.get('gender'),
                date_of_birth=self.cleaned_data.get('date_of_birth'),
                marital_status=self.cleaned_data.get('marital_status'),
                mobile_number=self.cleaned_data.get('mobile_number'),
                alternate_mobile_number=self.cleaned_data.get('alternate_mobile_number'),
            )

        return user


class ClientProfileUpdateForm(forms.ModelForm):
    """
    Form for updating an existing ClientProfile.
    """

    email = forms.EmailField(
        label="Email Address",
        disabled=True,
        help_text="Email cannot be changed after registration"
    )

    profile_picture = forms.ImageField(
        label="Profile Picture",
        required=False,
        help_text="JPG or PNG format, at least 200x200px, max 5MB",
        validators=[validate_profile_picture],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png'
        })
    )

    address = forms.CharField(
        max_length=255,
        required=False,
        label="Residential Address",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your residential address'
        })
    )

    pincode = forms.CharField(
        max_length=6,
        required=False,
        label="Postal Code (Pincode)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '6-digit postal code',
            'maxlength': '6'
        })
    )

    class Meta:
        model = ClientProfile
        fields = (
            'first_name',
            'last_name',
            'gender',
            'date_of_birth',
            'marital_status',
            'mobile_number',
            'alternate_mobile_number',
            'profile_picture',
            'address',
            'pincode'
        )
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'marital_status': forms.Select(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'alternate_mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['gender'].required = True
        self.fields['date_of_birth'].required = True
        self.fields['marital_status'].required = True
        self.fields['mobile_number'].required = True
