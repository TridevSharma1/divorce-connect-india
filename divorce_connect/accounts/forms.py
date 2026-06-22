from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import BaseUser


class BaseUserCreationForm(UserCreationForm):
    """
    Form for creating a new BaseUser instance.
    Handles email as the primary authentication field and password validation.
    """

    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        }),
        help_text="Password must be at least 8 characters long."
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = BaseUser
        fields = ('email', 'password1', 'password2')

    def clean_email(self):
        """Validate that the email is unique."""
        email = self.cleaned_data.get('email')
        if BaseUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        return email

    def clean_password2(self):
        """Validate that password1 and password2 match."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(
                    "The two password fields didn't match.",
                    code='password_mismatch',
                )
        return password2

    def save(self, commit=True):
        """Save the user with email as the primary identifier."""
        user = super().save(commit=False)
        user.username = user.email
        if commit:
            user.save()
        return user


class BaseUserAuthenticationForm(forms.Form):
    """
    Form for authenticating users using email and password.
    """

    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )

    def clean(self):
        """Validate email and password against the database."""
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(username=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(
                    "Invalid email or password. Please try again.",
                    code='invalid_login',
                )
        return self.cleaned_data

    def get_user(self):
        """Return the authenticated user instance."""
        return getattr(self, 'user_cache', None)


class BaseUserChangeForm(UserChangeForm):
    """
    Form for updating existing BaseUser instances.
    """

    class Meta:
        model = BaseUser
        fields = ('email', 'first_name', 'last_name')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
