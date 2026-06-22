# Quick Setup & Verification Checklist

## ✅ What's Been Implemented

### 1. **BaseUser Model** (accounts/models.py)
- ✅ Inherits from AbstractUser
- ✅ Email as USERNAME_FIELD (unique)
- ✅ Optional username field
- ✅ created_at, updated_at timestamps
- ✅ get_full_name() and get_short_name() methods

### 2. **Profile Models**
- ✅ ClientProfile (clients/models.py)
  - OneToOneField to BaseUser
  - All required fields with proper validators
  - Phone regex validator for mobile numbers
  - MaritalStatus and Gender choices

- ✅ LawyerProfile (lawyers/models.py)
  - OneToOneField to BaseUser
  - Bar registration (unique)
  - Specialization choices (9 options)
  - Rating (0.0-5.0)
  - Verified boolean
  - Database indexes for performance

- ✅ AdminPanelProfile (adminpanel/models.py)
  - OneToOneField to BaseUser
  - is_verified_by_superuser syncs with is_staff & is_active
  - Custom save() method for automatic sync

### 3. **Registration Forms**
- ✅ BaseUserCreationForm (accounts/forms.py)
  - Email validation with uniqueness check
  - password1 & password2 with match validation
  - HTML form widgets with Bootstrap classes

- ✅ ClientRegistrationForm (clients/forms.py)
  - Extends BaseUserCreationForm
  - All client-specific fields
  - Automatically creates ClientProfile on save()

- ✅ LawyerRegistrationForm (lawyers/forms.py)
  - Extends BaseUserCreationForm
  - All lawyer-specific fields
  - Bar registration uniqueness validation
  - Automatically creates LawyerProfile on save()

- ✅ AdminPanelRegistrationForm (adminpanel/forms.py)
  - Extends BaseUserCreationForm
  - All admin-specific fields
  - Automatically creates AdminPanelProfile (unverified)

- ✅ AdminVerificationForm (adminpanel/forms.py)
  - Simple checkbox form for superuser verification
  - Only is_verified_by_superuser field

### 4. **Admin Configurations**
- ✅ BaseUserAdmin (accounts/admin.py)
  - Email-based user lookup
  - Created_at and updated_at timestamps
  - Permissions management

- ✅ ClientProfileAdmin (clients/admin.py)
  - List display with email, phone, marital status
  - Filters by gender, marital status, join date
  - Search by name, email, phone

- ✅ LawyerProfileAdmin (lawyers/admin.py)
  - List display with rating and verification status
  - Bulk verify/unverify actions
  - Indexes for efficient queries

- ✅ AdminPanelProfileAdmin (adminpanel/admin.py)
  - Superuser-only permissions
  - Visual status indicators (green/red)
  - Bulk verify/unverify actions

### 5. **Settings Configuration**
- ✅ AUTH_USER_MODEL = 'accounts.BaseUser'
- ✅ accounts app added to INSTALLED_APPS (FIRST, before other apps)

---

## 🚀 Next Steps

### Step 1: Run Migrations
```bash
python manage.py makemigrations accounts
python manage.py makemigrations clients
python manage.py makemigrations lawyers
python manage.py makemigrations adminpanel

python manage.py migrate
```

### Step 2: Create Superuser
```bash
python manage.py createsuperuser
# Enter email, password when prompted
```

### Step 3: Test Admin Panel
```bash
python manage.py runserver
# Visit http://localhost:8000/admin
# Login with superuser credentials
```

---

## 📝 Key Features Summary

| Feature | Client | Lawyer | Admin |
|---------|--------|--------|-------|
| Email Login | ✅ | ✅ | ✅ |
| Password Hashed | ✅ | ✅ | ✅ |
| First/Last Name | ✅ | ✅ | ✅ |
| Gender Choice | ✅ | ✅ | ✅ |
| DOB | ✅ | ✅ | ✅ |
| Phone Number | ✅ | ✅ | ✅ |
| Marital Status | ✅ | - | - |
| Bar License | - | ✅ | - |
| Specialization | - | ✅ | - |
| Experience | - | ✅ | - |
| Rating | - | ✅ (0-5) | - |
| Verified | - | ✅ (admin) | ✅ (superuser) |
| Date Joined | ✅ | ✅ | ✅ |

---

## 🔒 Security Features

✅ **Password Security**
- PBKDF2 hashing with 600,000 iterations
- Django validators: length, common passwords, similarity
- password1 & password2 form validation (no plain text in models)

✅ **Email Validation**
- Unique constraint at model and form level
- Email format validation

✅ **Phone Validation**
- Regex validator: +?1?\d{9,15}
- International format support

✅ **Admin Security**
- Only superusers can create admin accounts
- Only superusers can verify admin accounts
- Automatic sync: verification → is_staff & is_active

✅ **OneToOne Relationships**
- No orphaned profiles (CASCADE delete)
- No duplicate profiles
- Unique constraint: one profile per user

---

## 📚 Related Names for Reverse Access

```python
# From BaseUser to Profile:
user.client_profile      # ClientProfile
user.lawyer_profile      # LawyerProfile
user.admin_profile       # AdminPanelProfile

# From Profile to BaseUser:
profile.user             # BaseUser instance
profile.user.email       # Access email directly
```

---

## 🧪 Example Usage

### Register a Client
```python
from clients.forms import ClientRegistrationForm

form_data = {
    'email': 'client@example.com',
    'password1': 'SecurePass123!',
    'password2': 'SecurePass123!',
    'first_name': 'John',
    'last_name': 'Doe',
    'gender': 'male',
    'date_of_birth': '1990-05-15',
    'marital_status': 'married',
    'mobile_number': '+919876543210',
    'alternate_mobile_number': '+919123456789',
}

form = ClientRegistrationForm(data=form_data)
if form.is_valid():
    user = form.save()  # Creates BaseUser + ClientProfile
    print(f"Created: {user.email}")
    print(f"Profile: {user.client_profile.marital_status}")
```

### Register a Lawyer
```python
from lawyers.forms import LawyerRegistrationForm

form_data = {
    'email': 'lawyer@example.com',
    'password1': 'SecurePass123!',
    'password2': 'SecurePass123!',
    'full_name': 'Jane Smith',
    'gender': 'female',
    'date_of_birth': '1985-08-20',
    'bar_registration_number': 'BCI/2016/12345',
    'state_bar_council': 'Bar Council of India - Delhi',
    'years_of_experience': 8,
    'specialization': 'family',
    'mobile_number': '+919876543210',
}

form = LawyerRegistrationForm(data=form_data)
if form.is_valid():
    user = form.save()  # Creates BaseUser + LawyerProfile
    print(f"Created: {user.email}")
    print(f"Verified: {user.lawyer_profile.verified}")  # False until admin verifies
```

### Register an Admin (Superuser Only)
```python
from adminpanel.forms import AdminPanelRegistrationForm
from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def create_admin_view(request):
    form_data = {
        'email': 'admin@example.com',
        'password1': 'SecurePass123!',
        'password2': 'SecurePass123!',
        'full_name': 'Admin User',
        'gender': 'other',
        'mobile_number': '+919876543210',
    }
    
    form = AdminPanelRegistrationForm(data=form_data)
    if form.is_valid():
        user = form.save()  # Creates BaseUser + AdminPanelProfile (unverified)
        print(f"Created: {user.email}")
        print(f"Is Staff: {user.is_staff}")  # False until verified
```

### Login
```python
from django.contrib.auth import authenticate, login

email = 'client@example.com'
password = 'SecurePass123!'

user = authenticate(request, username=email, password=password)
if user is not None:
    login(request, user)
    print(f"Logged in as: {user.email}")
```

---

## 📋 Choices Reference

### Gender (All Profiles)
- `'male'` → "Male"
- `'female'` → "Female"
- `'other'` → "Other"

### Marital Status (Clients Only)
- `'single'` → "Single"
- `'married'` → "Married"
- `'divorced'` → "Divorced"
- `'widowed'` → "Widowed"
- `'separated'` → "Separated"

### Specialization (Lawyers Only)
- `'criminal'` → "Criminal Law"
- `'family'` → "Family Law"
- `'corporate'` → "Corporate Law"
- `'ip'` → "Intellectual Property"
- `'labor'` → "Labor Law"
- `'tax'` → "Tax Law"
- `'real_estate'` → "Real Estate"
- `'bankruptcy'` → "Bankruptcy Law"
- `'other'` → "Other"

---

## 🐛 Troubleshooting

**Q: Import errors when running manage.py?**
A: Ensure `accounts` app is in INSTALLED_APPS BEFORE other apps

**Q: "AUTH_USER_MODEL refers to model that has not been installed"?**
A: Set AUTH_USER_MODEL in settings.py BEFORE first migration

**Q: Phone validation failing?**
A: Format must match regex: +?1?\d{9,15} (e.g., +919876543210)

**Q: Bar registration error on duplicate?**
A: Bar registration number must be unique per lawyer

**Q: Profile not created when user saves?**
A: Use form.save() from the Profile form, not BaseUser form directly

---

## 📖 File Structure

```
divorce_connect/
├── accounts/
│   ├── models.py          # ✅ BaseUser model
│   ├── forms.py           # ✅ BaseUser forms + auth
│   ├── admin.py           # ✅ Django admin config
│   └── ...
├── clients/
│   ├── models.py          # ✅ ClientProfile model
│   ├── forms.py           # ✅ ClientRegistrationForm
│   ├── admin.py           # ✅ Django admin config
│   └── ...
├── lawyers/
│   ├── models.py          # ✅ LawyerProfile model
│   ├── forms.py           # ✅ LawyerRegistrationForm
│   ├── admin.py           # ✅ Django admin config
│   └── ...
├── adminpanel/
│   ├── models.py          # ✅ AdminPanelProfile model
│   ├── forms.py           # ✅ Admin registration + verification forms
│   ├── admin.py           # ✅ Django admin config
│   └── ...
├── divorce_connect/
│   └── settings.py        # ✅ AUTH_USER_MODEL configured
└── AUTHENTICATION_ARCHITECTURE.md  # ✅ Full documentation
```

---

## ✨ Best Practices Implemented

✅ Single custom AUTH_USER_MODEL
✅ Email-based authentication
✅ OneToOne relationships for profiles
✅ Password never in model fields
✅ Validators for data integrity
✅ Django Choices for enum-like fields
✅ Proper admin configuration
✅ Related names for reverse access
✅ Timestamps for audit trails
✅ Custom save() for complex logic
✅ Bootstrap HTML form widgets
✅ Permission-based access control

---

**Ready to use!** 🎉
