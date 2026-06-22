from django import forms
from accounts.models import BaseUser
from accounts.forms import BaseUserCreationForm
from .models import ClientProfile, MaritalStatus, Gender


class ClientRegistrationForm(BaseUserCreationForm):
    """
    Extended registration form for Client users.
    Combines BaseUser creation with ClientProfile creation in a single form.
    """

    # Personal Information
    first_name = forms.CharField(
        max_length=50,
        label="First Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )

    last_name = forms.CharField(
        max_length=50,
        label="Last Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
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

    marital_status = forms.ChoiceField(
        choices=MaritalStatus.choices,
        label="Marital Status",
        widget=forms.Select(attrs={'class': 'form-control'})
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

    class Meta:
        model = ClientProfile
        fields = (
            'first_name',
            'last_name',
            'gender',
            'date_of_birth',
            'marital_status',
            'mobile_number',
            'alternate_mobile_number'
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
