from django import forms
from accounts.models import BaseUser
from accounts.forms import BaseUserCreationForm
from .models import LawyerProfile, Specialization, Gender, CaseDocument, CaseDocumentVerification, CaseRequest
from core_utils import validate_profile_picture


class LawyerRegistrationForm(BaseUserCreationForm):
    """
    Extended registration form for Lawyer users.
    Combines BaseUser creation with LawyerProfile creation in a single form.
    """

    # Personal Information
    full_name = forms.CharField(
        max_length=100,
        required=True,
        label="Full Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter full name'
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

    # Professional Information
    bar_registration_number = forms.CharField(
        max_length=50,
        required=True,
        label="Bar Registration Number",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., DL/2020/12345'
        })
    )

    state_bar_council = forms.CharField(
        max_length=100,
        required=True,
        label="State Bar Council",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Bar Council of India - Delhi'
        })
    )

    years_of_experience = forms.IntegerField(
        required=True,
        label="Years of Experience",
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter years of experience'
        })
    )

    specialization = forms.ChoiceField(
        required=True,
        choices=Specialization.choices,
        label="Legal Specialization",
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
            'full_name',
            'gender',
            'date_of_birth',
            'bar_registration_number',
            'state_bar_council',
            'years_of_experience',
            'specialization',
            'mobile_number',
            'alternate_mobile_number',
            'password1',
            'password2'
        )

    def clean_bar_registration_number(self):
        """Validate that bar registration number is unique."""
        bar_number = self.cleaned_data.get('bar_registration_number')
        if LawyerProfile.objects.filter(bar_registration_number=bar_number).exists():
            raise forms.ValidationError(
                "This bar registration number is already registered."
            )
        return bar_number

    def save(self, commit=True):
        """
        Save BaseUser instance and create associated LawyerProfile.
        """
        user = super().save(commit=commit)

        if commit:
            LawyerProfile.objects.create(
                user=user,
                full_name=self.cleaned_data.get('full_name'),
                gender=self.cleaned_data.get('gender'),
                date_of_birth=self.cleaned_data.get('date_of_birth'),
                bar_registration_number=self.cleaned_data.get('bar_registration_number'),
                state_bar_council=self.cleaned_data.get('state_bar_council'),
                years_of_experience=self.cleaned_data.get('years_of_experience'),
                specialization=self.cleaned_data.get('specialization'),
                mobile_number=self.cleaned_data.get('mobile_number'),
                alternate_mobile_number=self.cleaned_data.get('alternate_mobile_number'),
            )

        return user


class LawyerProfileUpdateForm(forms.ModelForm):
    """
    Form for updating an existing LawyerProfile.
    Note: Bar registration number cannot be changed.
    """

    email = forms.EmailField(
        label="Email Address",
        disabled=True,
        help_text="Email cannot be changed after registration"
    )

    bar_registration_number = forms.CharField(
        label="Bar Registration Number",
        disabled=True,
        help_text="Bar registration number cannot be changed"
    )

    class Meta:
        model = LawyerProfile
        fields = (
            'full_name',
            'gender',
            'date_of_birth',
            'state_bar_council',
            'years_of_experience',
            'specialization',
            'mobile_number',
            'alternate_mobile_number',
            'bar_registration_number'
        )
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'state_bar_council': forms.TextInput(attrs={'class': 'form-control'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'form-control'}),
            'specialization': forms.Select(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'alternate_mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email


class LawyerProfileEditForm(forms.ModelForm):
    """
    Form for completing lawyer profile during onboarding.
    All fields are required to ensure complete profile submission.
    Used when lawyer redirects from registration to edit profile.
    """

    email = forms.EmailField(
        label="Email Address",
        disabled=True,
        help_text="Email cannot be changed after registration"
    )

    bar_registration_number = forms.CharField(
        max_length=50,
        label="Bar Registration Number",
        help_text="Enter your actual bar council registration number",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., DL/2020/12345'
        })
    )

    state_bar_council = forms.CharField(
        max_length=100,
        label="State Bar Council",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Bar Council of India - Delhi'
        })
    )

    mobile_number = forms.CharField(
        max_length=13,
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

    consultation_fee = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label="Consultation Fee (₹)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your hourly consultation fee in rupees'
        })
    )

    profile_picture = forms.ImageField(
        label="Profile Picture",
        required=True,
        help_text="JPG or PNG format, at least 200x200px, max 5MB",
        validators=[validate_profile_picture],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png'
        })
    )

    class Meta:
        model = LawyerProfile
        fields = (
            'full_name',
            'gender',
            'date_of_birth',
            'bar_registration_number',
            'state_bar_council',
            'years_of_experience',
            'specialization',
            'mobile_number',
            'alternate_mobile_number',
            'consultation_fee',
            'profile_picture'
        )
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'years_of_experience': forms.NumberInput(attrs={'class': 'form-control'}),
            'specialization': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
        self.fields['full_name'].required = True
        self.fields['gender'].required = True
        self.fields['date_of_birth'].required = True
        self.fields['bar_registration_number'].required = True
        self.fields['state_bar_council'].required = True
        self.fields['years_of_experience'].required = True
        self.fields['specialization'].required = True
        self.fields['mobile_number'].required = True
        self.fields['consultation_fee'].required = True


class CaseDocumentUploadForm(forms.ModelForm):
    """Form for uploading case documents."""

    class Meta:
        model = CaseDocument
        fields = ['document_type', 'document_file']
        widgets = {
            'document_type': forms.Select(attrs={
                'class': 'form-control',
                'disabled': True
            }),
            'document_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.docx'
            })
        }

    def __init__(self, *args, **kwargs):
        self.case_request = kwargs.pop('case_request', None)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['document_type'].disabled = True
            self.fields['document_type'].widget = forms.HiddenInput()


class CaseDocumentBulkUploadForm(forms.Form):
    """Form for bulk uploading multiple case documents."""

    aadhaar = forms.FileField(
        required=False,
        label="Aadhaar Card",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.docx'
        })
    )

    pan = forms.FileField(
        required=False,
        label="PAN Card",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.docx'
        })
    )

    marriage_cert = forms.FileField(
        required=False,
        label="Marriage Certificate",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.docx'
        })
    )

    address_proof = forms.FileField(
        required=False,
        label="Address Proof",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.docx'
        })
    )

    income_proof = forms.FileField(
        required=False,
        label="Income Proof",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.docx'
        })
    )

    passport = forms.FileField(
        required=False,
        label="Passport",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.docx'
        })
    )

    affidavit = forms.FileField(
        required=False,
        label="Affidavits",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.docx'
        })
    )

    def __init__(self, *args, **kwargs):
        self.case_request = kwargs.pop('case_request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        # Check if at least one document is uploaded
        document_types = ['aadhaar', 'pan', 'marriage_cert', 'address_proof', 'income_proof', 'passport', 'affidavit']
        documents_uploaded = any(
            cleaned_data.get(doc_type) for doc_type in document_types
        )
        if not documents_uploaded:
            raise forms.ValidationError("Please upload at least one document.")
        return cleaned_data


class DocumentVerificationForm(forms.ModelForm):
    """Form for admin to verify case documents."""

    class Meta:
        model = CaseDocumentVerification
        fields = ['status', 'rejection_reason']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Explain reason for rejection (if applicable)'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide rejection reason field if status is not rejection
        if self.instance.status != 'REJECTED':
            self.fields['rejection_reason'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')

        if status == 'REJECTED' and not rejection_reason:
            raise forms.ValidationError(
                "Please provide a rejection reason when rejecting a document."
            )
        return cleaned_data
