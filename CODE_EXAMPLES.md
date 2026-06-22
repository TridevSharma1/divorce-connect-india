# Code Examples - Multi-Role Authentication System

## Table of Contents
1. [Registration Views](#registration-views)
2. [Login Views](#login-views)
3. [Profile Access](#profile-access)
4. [Admin Operations](#admin-operations)
5. [Query Examples](#query-examples)
6. [API Responses](#api-responses)
7. [Testing](#testing)

---

## Registration Views

### Client Registration View

```python
# clients/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from clients.forms import ClientRegistrationForm

def register_client(request):
    """
    Handle client registration.
    Creates both BaseUser and ClientProfile in a single transaction.
    """
    if request.method == 'POST':
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # BaseUser + ClientProfile created
            login(request, user)  # Log user in immediately
            return redirect('client_dashboard')  # Or your dashboard URL
    else:
        form = ClientRegistrationForm()
    
    return render(request, 'clients/register.html', {'form': form})
```

### Lawyer Registration View

```python
# lawyers/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from lawyers.forms import LawyerRegistrationForm

def register_lawyer(request):
    """
    Handle lawyer registration.
    Creates both BaseUser and LawyerProfile in a single transaction.
    Note: Lawyer starts as unverified (verified=False).
    """
    if request.method == 'POST':
        form = LawyerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # BaseUser + LawyerProfile created
            login(request, user)  # Log user in immediately
            
            # Show message that account is pending verification
            messages.info(
                request,
                'Your account has been created successfully. '
                'Admin will verify your credentials shortly.'
            )
            return redirect('lawyer_dashboard')
    else:
        form = LawyerRegistrationForm()
    
    return render(request, 'lawyers/register.html', {'form': form})
```

### Admin Registration View (Superuser Only)

```python
# adminpanel/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from adminpanel.forms import AdminPanelRegistrationForm

@user_passes_test(lambda u: u.is_superuser)
def register_admin(request):
    """
    Handle admin registration.
    ONLY accessible to superusers.
    Creates both BaseUser and AdminPanelProfile in a single transaction.
    Note: Admin starts as unverified (is_verified_by_superuser=False).
    """
    if request.method == 'POST':
        form = AdminPanelRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # BaseUser + AdminPanelProfile created (unverified)
            
            messages.success(
                request,
                f'Admin account for {user.email} created. '
                f'Please verify in the admin panel to activate.'
            )
            return redirect('admin:adminpanel_adminpanelprofile_change')
    else:
        form = AdminPanelRegistrationForm()
    
    return render(request, 'adminpanel/register_admin.html', {'form': form})
```

---

## Login Views

### Email-Based Authentication

```python
# accounts/views.py
from django import forms
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

class EmailAuthenticationForm(forms.Form):
    """Simple form for email/password authentication."""
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

def login_view(request):
    """
    Handle user login using email and password.
    Supports all user types: Client, Lawyer, Admin.
    """
    if request.method == 'POST':
        form = EmailAuthenticationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            # Django uses USERNAME_FIELD='email'
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                if not user.is_active:
                    messages.error(request, 'This account is disabled.')
                    return render(request, 'accounts/login.html', {'form': form})
                
                login(request, user)
                return redirect_by_user_type(user)  # See function below
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = EmailAuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def redirect_by_user_type(user):
    """Redirect user to appropriate dashboard based on their type."""
    if hasattr(user, 'client_profile'):
        return redirect('client_dashboard')
    elif hasattr(user, 'lawyer_profile'):
        return redirect('lawyer_dashboard')
    elif hasattr(user, 'admin_profile'):
        return redirect('admin:index')
    else:
        return redirect('home')

@login_required
def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')
```

### Using BaseUserAuthenticationForm

```python
# accounts/views.py (alternative approach)
from accounts.forms import BaseUserAuthenticationForm

def login_view_alt(request):
    """Alternative login using BaseUserAuthenticationForm."""
    if request.method == 'POST':
        form = BaseUserAuthenticationForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect_by_user_type(user)
    else:
        form = BaseUserAuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})
```

---

## Profile Access

### Access Profile from User Instance

```python
from accounts.models import BaseUser

# Get user
user = BaseUser.objects.get(email='user@example.com')

# Access based on user type
if hasattr(user, 'client_profile'):
    profile = user.client_profile
    print(f"Client: {profile.first_name} {profile.last_name}")
    print(f"Marital Status: {profile.marital_status}")
    
elif hasattr(user, 'lawyer_profile'):
    profile = user.lawyer_profile
    print(f"Lawyer: {profile.full_name}")
    print(f"Specialization: {profile.specialization}")
    print(f"Verified: {profile.verified}")
    
elif hasattr(user, 'admin_profile'):
    profile = user.admin_profile
    print(f"Admin: {profile.full_name}")
    print(f"Is Verified: {profile.is_verified_by_superuser}")
```

### Get User Type

```python
def get_user_role(user):
    """Return the role of the user."""
    if hasattr(user, 'client_profile'):
        return 'CLIENT'
    elif hasattr(user, 'lawyer_profile'):
        return 'LAWYER'
    elif hasattr(user, 'admin_profile'):
        return 'ADMIN'
    return None

# Usage
role = get_user_role(request.user)
print(f"User role: {role}")
```

### Access User from Profile

```python
from clients.models import ClientProfile

# Get profile
profile = ClientProfile.objects.first()

# Access user info
print(f"Email: {profile.user.email}")
print(f"Is Active: {profile.user.is_active}")
print(f"Name: {profile.user.get_full_name()}")
```

### Update Profile

```python
# Update client profile
client_profile = user.client_profile
client_profile.marital_status = 'married'
client_profile.mobile_number = '+919876543210'
client_profile.save()

# Update lawyer profile
lawyer_profile = user.lawyer_profile
lawyer_profile.years_of_experience = 10
lawyer_profile.specialization = 'family'
lawyer_profile.save()

# Update admin profile
admin_profile = user.admin_profile
admin_profile.full_name = 'New Name'
admin_profile.save()  # This also syncs is_staff and is_active
```

---

## Admin Operations

### Verify a Lawyer

```python
from lawyers.models import LawyerProfile
from django.contrib import messages

def verify_lawyer(lawyer_id):
    """Verify a lawyer's credentials (admin operation)."""
    try:
        lawyer = LawyerProfile.objects.get(id=lawyer_id)
        lawyer.verified = True
        lawyer.save()
        return True
    except LawyerProfile.DoesNotExist:
        return False

# Usage
if verify_lawyer(1):
    print("Lawyer verified successfully")
```

### Verify and Activate Admin

```python
from adminpanel.models import AdminPanelProfile

def verify_admin_account(admin_id):
    """Verify and activate admin account (superuser only)."""
    try:
        admin = AdminPanelProfile.objects.get(id=admin_id)
        admin.is_verified_by_superuser = True
        admin.save()  # This triggers the save() method which syncs to BaseUser
        
        # Verify the sync happened
        assert admin.user.is_staff == True
        assert admin.user.is_active == True
        return True
    except AdminPanelProfile.DoesNotExist:
        return False

# Usage
if verify_admin_account(1):
    print("Admin account activated successfully")
```

### Deactivate Admin

```python
def deactivate_admin_account(admin_id):
    """Deactivate admin account (superuser only)."""
    try:
        admin = AdminPanelProfile.objects.get(id=admin_id)
        admin.is_verified_by_superuser = False
        admin.save()  # This triggers the save() method
        
        # Verify the sync happened
        assert admin.user.is_staff == False
        assert admin.user.is_active == False
        return True
    except AdminPanelProfile.DoesNotExist:
        return False
```

### Rate a Lawyer

```python
def rate_lawyer(lawyer_id, rating):
    """Set or update lawyer's rating (0.0 to 5.0)."""
    if not (0.0 <= rating <= 5.0):
        raise ValueError("Rating must be between 0.0 and 5.0")
    
    try:
        lawyer = LawyerProfile.objects.get(id=lawyer_id)
        lawyer.rating = rating
        lawyer.save()
        return True
    except LawyerProfile.DoesNotExist:
        return False

# Usage
rate_lawyer(1, 4.5)  # Rate lawyer with ID 1 as 4.5 stars
```

---

## Query Examples

### Find Clients by Marital Status

```python
from clients.models import ClientProfile, MaritalStatus

# Find all married clients
married_clients = ClientProfile.objects.filter(
    marital_status=MaritalStatus.MARRIED
)

# Find all divorced clients
divorced_clients = ClientProfile.objects.filter(
    marital_status=MaritalStatus.DIVORCED
)
```

### Find Verified Lawyers by Specialization

```python
from lawyers.models import LawyerProfile, Specialization

# Find all verified family law lawyers
family_lawyers = LawyerProfile.objects.filter(
    verified=True,
    specialization=Specialization.FAMILY
).order_by('-rating')

# Find all criminal law lawyers with experience
criminal_lawyers = LawyerProfile.objects.filter(
    specialization=Specialization.CRIMINAL,
    years_of_experience__gte=5
).order_by('-rating')

# Find top-rated lawyers
top_lawyers = LawyerProfile.objects.filter(
    verified=True,
    rating__gte=4.0
).order_by('-rating')[:10]
```

### Find Active Users by Role

```python
from accounts.models import BaseUser

# Find active clients
active_clients = BaseUser.objects.filter(
    is_active=True,
    client_profile__isnull=False
)

# Find active verified lawyers
active_lawyers = BaseUser.objects.filter(
    is_active=True,
    lawyer_profile__verified=True
)

# Find active admins
active_admins = BaseUser.objects.filter(
    is_staff=True,
    is_active=True,
    admin_profile__is_verified_by_superuser=True
)
```

### Search Users

```python
from django.db.models import Q

# Search for clients by name or email
search_term = 'john'
clients = ClientProfile.objects.filter(
    Q(first_name__icontains=search_term) |
    Q(last_name__icontains=search_term) |
    Q(user__email__icontains=search_term)
)

# Search for lawyers by name, bar number, or email
lawyers = LawyerProfile.objects.filter(
    Q(full_name__icontains=search_term) |
    Q(bar_registration_number__icontains=search_term) |
    Q(user__email__icontains=search_term)
)
```

### Recent Registrations

```python
from datetime import timedelta
from django.utils import timezone

# Clients registered in last 7 days
recent_clients = ClientProfile.objects.filter(
    date_of_join__gte=timezone.now() - timedelta(days=7)
).order_by('-date_of_join')

# Lawyers registered in last 30 days
recent_lawyers = LawyerProfile.objects.filter(
    date_joined__gte=timezone.now() - timedelta(days=30)
).order_by('-date_joined')
```

---

## API Responses

### Successful Client Registration Response

```json
{
  "status": "success",
  "message": "Client registered successfully",
  "user": {
    "id": 1,
    "email": "john.doe@example.com",
    "created_at": "2024-06-22T10:30:00Z"
  },
  "profile": {
    "id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "gender": "male",
    "marital_status": "married",
    "mobile_number": "+919876543210",
    "date_of_join": "2024-06-22T10:30:00Z"
  }
}
```

### Successful Lawyer Registration Response

```json
{
  "status": "success",
  "message": "Lawyer registered successfully. Pending admin verification.",
  "user": {
    "id": 2,
    "email": "jane.smith@example.com",
    "created_at": "2024-06-22T11:00:00Z"
  },
  "profile": {
    "id": 1,
    "full_name": "Jane Smith",
    "specialization": "family",
    "years_of_experience": 8,
    "bar_registration_number": "BCI/2016/12345",
    "verified": false,
    "rating": 0.0,
    "date_joined": "2024-06-22T11:00:00Z"
  }
}
```

### Login Success Response

```json
{
  "status": "success",
  "message": "Login successful",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "role": "CLIENT"
  },
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Login Failed Response

```json
{
  "status": "error",
  "message": "Invalid email or password"
}
```

### Validation Error Response

```json
{
  "status": "error",
  "errors": {
    "email": ["This email address is already registered."],
    "password2": ["The two password fields didn't match."],
    "mobile_number": ["Phone number must be entered in the format: '+999999999'"]
  }
}
```

---

## Testing

### Unit Tests

```python
# accounts/tests.py
from django.test import TestCase
from accounts.models import BaseUser

class BaseUserModelTests(TestCase):
    def setUp(self):
        self.user = BaseUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_created_with_email(self):
        self.assertEqual(self.user.email, 'test@example.com')
    
    def test_username_field_is_email(self):
        self.assertEqual(BaseUser.USERNAME_FIELD, 'email')
    
    def test_password_is_hashed(self):
        self.assertNotEqual(self.user.password, 'testpass123')
    
    def test_authenticate_with_email(self):
        from django.contrib.auth import authenticate
        user = authenticate(username='test@example.com', password='testpass123')
        self.assertIsNotNone(user)
```

### Form Tests

```python
# clients/tests.py
from django.test import TestCase
from clients.forms import ClientRegistrationForm

class ClientRegistrationFormTests(TestCase):
    def test_valid_form(self):
        form_data = {
            'email': 'client@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'male',
            'marital_status': 'married',
            'mobile_number': '+919876543210',
        }
        form = ClientRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_password_mismatch(self):
        form_data = {
            'email': 'client@example.com',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'male',
            'marital_status': 'married',
            'mobile_number': '+919876543210',
        }
        form = ClientRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
```

### Integration Tests

```python
# clients/tests.py
from django.test import TestCase, Client as TestClient
from clients.models import ClientProfile
from accounts.models import BaseUser

class ClientRegistrationIntegrationTests(TestCase):
    def setUp(self):
        self.client = TestClient()
    
    def test_client_registration_flow(self):
        response = self.client.post('/register/client/', {
            'email': 'newclient@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'male',
            'marital_status': 'married',
            'mobile_number': '+919876543210',
        })
        
        # User created
        self.assertTrue(BaseUser.objects.filter(
            email='newclient@example.com'
        ).exists())
        
        # Profile created
        self.assertTrue(ClientProfile.objects.filter(
            first_name='John',
            last_name='Doe'
        ).exists())
        
        # Redirected (status 302)
        self.assertEqual(response.status_code, 302)
```

---

**Version**: 1.0
**Last Updated**: 2024-06-22
