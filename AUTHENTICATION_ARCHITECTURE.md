# Multi-Role User Authentication System - Documentation

## Architecture Overview

This Django project implements an **industry-best-practice** multi-role user authentication system using a **single custom BaseUser model** with separate Profile models for each user type.

### Key Design Principles

1. **Single AUTH_USER_MODEL**: All authentication goes through `accounts.BaseUser`
2. **Email-based Authentication**: Users login using email instead of username
3. **Separation of Concerns**: Authentication (BaseUser) is separate from role-specific data (Profile models)
4. **OneToOne Relationships**: Each profile links to BaseUser via OneToOneField
5. **Secure Password Handling**: Password and confirm_password are NOT model fields; they're form-only

---

## Database Structure

### 1. BaseUser Model (accounts/models.py)
- **AUTH_USER_MODEL**: `accounts.BaseUser`
- **Inheritance**: Extends `AbstractUser`
- **Primary Key**: `id` (auto-generated)
- **Username Field**: `email` (unique, used for login)
- **Key Fields**:
  - `email` (unique, max_length=254) - Used for authentication
  - `password` - Hashed by Django
  - `first_name`, `last_name` - From AbstractUser
  - `created_at`, `updated_at` - Timestamps
  - `is_active`, `is_staff`, `is_superuser` - Permissions

### 2. ClientProfile Model (clients/models.py)
- **Relation**: OneToOneField to BaseUser
- **Key Fields**:
  - `first_name`, `last_name` - Client's name
  - `email` - Via BaseUser (not stored here)
  - `gender` - Choice field (Male, Female, Other)
  - `date_of_birth` - Optional DOB
  - `marital_status` - Choice field (Single, Married, Divorced, Widowed, Separated)
  - `mobile_number` - Validated phone number
  - `alternate_mobile_number` - Optional alternate phone
  - `date_of_join` - Auto-added timestamp

### 3. LawyerProfile Model (lawyers/models.py)
- **Relation**: OneToOneField to BaseUser
- **Key Fields**:
  - `full_name` - Lawyer's complete name
  - `gender` - Choice field
  - `date_of_birth` - Optional DOB
  - `bar_registration_number` - Unique, required for verification
  - `state_bar_council` - State bar authority name
  - `years_of_experience` - Integer, >= 0
  - `specialization` - Choice field (Criminal, Family, Corporate, IP, Labor, Tax, Real Estate, Bankruptcy, Other)
  - `rating` - Float, 0.0-5.0 scale
  - `verified` - Boolean, admin-verified credentials
  - `mobile_number` - Validated phone
  - `alternate_mobile_number` - Optional alternate
  - `date_joined` - Auto-added timestamp

### 4. AdminPanelProfile Model (adminpanel/models.py)
- **Relation**: OneToOneField to BaseUser
- **Key Fields**:
  - `full_name` - Admin's complete name
  - `gender` - Choice field
  - `date_of_birth` - Optional DOB
  - `mobile_number` - Validated phone
  - `alternate_mobile_number` - Optional alternate
  - `is_verified_by_superuser` - Boolean, auto-syncs with BaseUser.is_staff & is_active
  - `date_of_join` - Auto-added timestamp

---

## Registration Forms

### BaseUserCreationForm (accounts/forms.py)
**Purpose**: Core user creation form using Django's UserCreationForm

**Fields**:
- `email` - Unique email address
- `password1` - Password
- `password2` - Confirm password (validated to match password1)

**Validation**:
- Email uniqueness check
- Password strength (Django defaults: min 8 chars, common password check, etc.)
- Password confirmation match
- No personal info similarity to password

**Usage**:
```python
from accounts.forms import BaseUserCreationForm

if request.method == 'POST':
    form = BaseUserCreationForm(request.POST)
    if form.is_valid():
        user = form.save()  # BaseUser created with email as username
```

---

### ClientRegistrationForm (clients/forms.py)
**Purpose**: Register a new Client (extends BaseUserCreationForm)

**Fields**:
- `email` - Inherited from BaseUserCreationForm
- `password1`, `password2` - Inherited from BaseUserCreationForm
- `first_name` - Client's first name
- `last_name` - Client's last name
- `gender` - Choice (Male, Female, Other)
- `date_of_birth` - Optional DOB
- `marital_status` - Choice (Single, Married, Divorced, Widowed, Separated)
- `mobile_number` - Required phone
- `alternate_mobile_number` - Optional alternate phone

**Validation**:
- Inherits all BaseUserCreationForm validations
- Phone number format validation (RegexValidator: +1 to 15 digits)

**What It Does on Save**:
1. Creates BaseUser with email as username
2. Creates ClientProfile linked to the BaseUser
3. All passwords are hashed before storage

**Usage**:
```python
from clients.forms import ClientRegistrationForm

if request.method == 'POST':
    form = ClientRegistrationForm(request.POST)
    if form.is_valid():
        user = form.save()  # Creates BaseUser + ClientProfile
        client_profile = user.client_profile  # Access via related_name
```

---

### LawyerRegistrationForm (lawyers/forms.py)
**Purpose**: Register a new Lawyer (extends BaseUserCreationForm)

**Fields**:
- `email` - Inherited from BaseUserCreationForm
- `password1`, `password2` - Inherited from BaseUserCreationForm
- `full_name` - Lawyer's full name
- `gender` - Choice (Male, Female, Other)
- `date_of_birth` - Optional DOB
- `bar_registration_number` - Unique bar license number
- `state_bar_council` - Bar council name (e.g., "Bar Council of India - Delhi")
- `years_of_experience` - Integer >= 0
- `specialization` - Choice (Criminal, Family, Corporate, IP, Labor, Tax, Real Estate, Bankruptcy, Other)
- `mobile_number` - Required phone
- `alternate_mobile_number` - Optional alternate phone

**Validation**:
- Inherits all BaseUserCreationForm validations
- Bar registration number uniqueness check
- Phone number format validation
- Years of experience >= 0

**What It Does on Save**:
1. Creates BaseUser with email as username
2. Creates LawyerProfile linked to the BaseUser
3. `verified` is set to False (admin must verify credentials)
4. `rating` defaults to 0.0

**Usage**:
```python
from lawyers.forms import LawyerRegistrationForm

if request.method == 'POST':
    form = LawyerRegistrationForm(request.POST)
    if form.is_valid():
        user = form.save()  # Creates BaseUser + LawyerProfile
        lawyer_profile = user.lawyer_profile  # Access via related_name
```

---

### AdminPanelRegistrationForm (adminpanel/forms.py)
**Purpose**: Register a new Admin (extends BaseUserCreationForm)

**⚠️ IMPORTANT**: This form should ONLY be used in superuser-only views!

**Fields**:
- `email` - Inherited from BaseUserCreationForm
- `password1`, `password2` - Inherited from BaseUserCreationForm
- `full_name` - Admin's full name
- `gender` - Choice (Male, Female, Other)
- `date_of_birth` - Optional DOB
- `mobile_number` - Required phone
- `alternate_mobile_number` - Optional alternate phone

**Validation**:
- Inherits all BaseUserCreationForm validations
- Phone number format validation

**What It Does on Save**:
1. Creates BaseUser with email as username
2. Creates AdminPanelProfile linked to the BaseUser
3. `is_verified_by_superuser` is set to False (must be manually verified)
4. BaseUser.is_staff and is_active are initially False

**Security Notes**:
- Only superusers can create admin accounts (enforced in views)
- Accounts start as inactive and non-staff
- A superuser must explicitly verify (check `is_verified_by_superuser`)
- This triggers automatic sync: BaseUser.is_staff = True, is_active = True

**Usage**:
```python
from adminpanel.forms import AdminPanelRegistrationForm
from django.contrib.admin.decorators import permission_required

@permission_required('is_superuser')
def create_admin_view(request):
    if request.method == 'POST':
        form = AdminPanelRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Creates BaseUser + AdminPanelProfile (unverified)
            admin_profile = user.admin_profile  # Access via related_name
```

---

### AdminVerificationForm (adminpanel/forms.py)
**Purpose**: Simple form for superusers to verify/activate admin accounts

**Fields**:
- `is_verified_by_superuser` - Checkbox

**Usage**:
```python
from adminpanel.forms import AdminVerificationForm

# In Django admin, superusers can click a checkbox to verify
admin_profile = AdminPanelProfile.objects.get(id=1)
form = AdminVerificationForm(instance=admin_profile)

# When saved, automatically syncs to BaseUser
if form.is_valid():
    form.save()  # Calls AdminPanelProfile.save() which updates BaseUser
```

---

## Password & Confirm Password Logic

### How It Works (Secure)

**Model Fields**: NO password fields in Profile models
- Passwords are NEVER stored in Profile models
- Passwords are ONLY in BaseUser.password (Django-managed, hashed)

**Form Fields**: YES, password1 and password2 in registration forms
- `password1` and `password2` are form-only fields
- They inherit from UserCreationForm's clean_password2() method
- Validation ensures they match before saving

**Hashing**: Django's PBKDF2 algorithm (default)
- When form.save() is called, Django automatically hashes the password
- User.set_password() is called internally by the base form

**Example Flow**:
```
User enters: password="SecurePass123", confirm_password="SecurePass123"
           ↓
Form validation checks they match
           ↓
form.save() calls User.set_password("SecurePass123")
           ↓
Django hashes it: "pbkdf2_sha256$600000$xyz..."
           ↓
Stored in BaseUser.password (hashed, never reversible)
```

---

## Authentication (Login)

### Using Django's authenticate()

```python
from django.contrib.auth import authenticate, login

# In a login view
email = request.POST['email']
password = request.POST['password']

# Django uses USERNAME_FIELD='email' to authenticate
user = authenticate(request, username=email, password=password)

if user is not None:
    login(request, user)
    # User is now authenticated
else:
    # Invalid credentials
```

### Using BaseUserAuthenticationForm

```python
from accounts.forms import BaseUserAuthenticationForm

form = BaseUserAuthenticationForm(data=request.POST)
if form.is_valid():
    user = form.get_user()
    login(request, user)
```

---

## Settings Configuration

Add to `settings.py`:

```python
# Set custom user model
AUTH_USER_MODEL = 'accounts.BaseUser'

# Installed apps (in order)
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts.apps.AccountsConfig',
    'clients.apps.ClientsConfig',
    'lawyers.apps.LawyersConfig',
    'adminpanel.apps.AdminpanelConfig',
]
```

---

## Django Admin Features

### BaseUserAdmin
- Email-based user lookup
- Manage permissions (is_staff, is_superuser)
- View created_at and updated_at timestamps

### ClientProfileAdmin
- List clients by name, email, marital status
- Filter by gender, marital status, join date
- Search by name, email, phone number

### LawyerProfileAdmin
- List lawyers with specialization, experience, rating
- Bulk verify lawyers with admin actions
- Filter by verification status and rating
- Search by name, email, bar registration

### AdminPanelProfileAdmin
- Restricted to superusers only
- Visual verification status indicators
- Bulk verify/unverify admin accounts
- Automatic syncing with BaseUser staff status

---

## Migration Strategy

```bash
# Create migrations for accounts app first
python manage.py makemigrations accounts

# Then create migrations for other apps
python manage.py makemigrations clients
python manage.py makemigrations lawyers
python manage.py makemigrations adminpanel

# Apply all migrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser
```

**Important**: Before running migrations, ensure `AUTH_USER_MODEL` is set in settings.py!

---

## Common Usage Patterns

### 1. Get User by Email
```python
from accounts.models import BaseUser

user = BaseUser.objects.get(email='user@example.com')
```

### 2. Access Profile from User
```python
# Client
client_profile = user.client_profile
print(client_profile.marital_status)

# Lawyer
lawyer_profile = user.lawyer_profile
print(lawyer_profile.specialization)

# Admin
admin_profile = user.admin_profile
print(admin_profile.is_verified_by_superuser)
```

### 3. Access User from Profile
```python
client = ClientProfile.objects.first()
email = client.user.email
is_active = client.user.is_active
```

### 4. Check User Type
```python
def get_user_type(user):
    if hasattr(user, 'client_profile'):
        return 'CLIENT'
    elif hasattr(user, 'lawyer_profile'):
        return 'LAWYER'
    elif hasattr(user, 'admin_profile'):
        return 'ADMIN'
    return None
```

### 5. Filter by Role
```python
# All verified lawyers
verified_lawyers = LawyerProfile.objects.filter(verified=True)

# All active clients
active_clients = ClientProfile.objects.filter(user__is_active=True)

# All admin users
admin_users = AdminPanelProfile.objects.filter(is_verified_by_superuser=True)
```

---

## Security Considerations

✓ **Passwords**: Hashed with PBKDF2, never stored in plain text
✓ **Email Uniqueness**: Enforced at model and form level
✓ **Admin Verification**: Only superusers can activate admin accounts
✓ **Phone Validation**: Regex validator ensures proper format
✓ **OneToOne Relationships**: Ensures no orphaned profiles
✓ **Related Names**: Prevent reverse relation conflicts

⚠️ **Remember**:
- Always use `authenticate()` function for login
- Never compare passwords directly with stored hashes
- Use `set_password()` when changing passwords
- Enforce permission checks in views (e.g., @login_required)

---

## API Response Examples

### Client Registration Success
```json
{
  "status": "success",
  "user": {
    "id": 1,
    "email": "client@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "profile": {
    "gender": "male",
    "marital_status": "married",
    "mobile_number": "+919876543210"
  }
}
```

### Lawyer Profile Data
```json
{
  "id": 1,
  "full_name": "Jane Smith",
  "email": "jane@example.com",
  "specialization": "family",
  "years_of_experience": 8,
  "rating": 4.5,
  "verified": true,
  "bar_registration_number": "BCI/2016/12345"
}
```

### Admin Profile Data
```json
{
  "id": 1,
  "full_name": "Admin User",
  "email": "admin@example.com",
  "is_verified_by_superuser": true,
  "date_of_join": "2024-01-15T10:30:00Z"
}
```

---

## Troubleshooting

### Issue: "AUTH_USER_MODEL refers to model that has not been installed"
**Solution**: Add `AUTH_USER_MODEL = 'accounts.BaseUser'` BEFORE running migrations

### Issue: "BaseUser matches multiple installed models"
**Solution**: Ensure only one app has a custom user model. Remove conflicting User models.

### Issue: Can't login with email
**Solution**: Ensure USERNAME_FIELD = 'email' in BaseUser model Meta, and use authenticate(username=email, password=password)

### Issue: Profile not created when user registers
**Solution**: Ensure Profile app is in INSTALLED_APPS and form.save(commit=True) is called

### Issue: AdminPanelProfile.save() not syncing to BaseUser
**Solution**: Always call admin_profile.save() (not just form.save() on the BaseUser alone)

---

## Next Steps

1. ✅ Models created and configured
2. ✅ Forms with password handling created
3. ✅ Django admin configured
4. ✅ Settings configured with AUTH_USER_MODEL
5. 📋 TODO: Create Views and URLs
6. 📋 TODO: Create Serializers (if using DRF)
7. 📋 TODO: Create Tests
8. 📋 TODO: Add Email Verification (optional)
9. 📋 TODO: Add JWT tokens (if using API)

---

**Version**: 1.0
**Last Updated**: 2024-06-22
**Django Version**: 6.0.3+
