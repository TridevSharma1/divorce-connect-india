# Quick Start Reference Card

## 🎯 For the Impatient: 5-Minute Setup

### Step 1: Make Migrations (2 min)
```bash
python manage.py makemigrations accounts clients lawyers adminpanel
python manage.py migrate
```

### Step 2: Create Admin (1 min)
```bash
python manage.py createsuperuser
```

### Step 3: Test It (2 min)
```bash
python manage.py runserver
# Visit http://localhost:8000/admin
```

**Done!** ✅ Ready to build views.

---

## 📋 Cheat Sheet

### Get User Type
```python
user = BaseUser.objects.get(email='user@example.com')
if hasattr(user, 'client_profile'): role = 'CLIENT'
elif hasattr(user, 'lawyer_profile'): role = 'LAWYER'
elif hasattr(user, 'admin_profile'): role = 'ADMIN'
```

### Register Client
```python
from clients.forms import ClientRegistrationForm
form = ClientRegistrationForm(data=request.POST)
if form.is_valid():
    user = form.save()  # Both BaseUser and ClientProfile created
```

### Login User
```python
from django.contrib.auth import authenticate, login
user = authenticate(request, username='user@example.com', password='pass')
if user:
    login(request, user)
```

### Access Profiles
```python
client_profile = user.client_profile       # Direct access
lawyer_profile = user.lawyer_profile
admin_profile = user.admin_profile
email = profile.user.email                 # Access back to user
```

### Query Patterns
```python
# Find users by type
ClientProfile.objects.filter(user__is_active=True)

# Find verified lawyers
LawyerProfile.objects.filter(verified=True).order_by('-rating')

# Find by email
BaseUser.objects.get(email='user@example.com')
```

---

## 🔐 Security Checklist

✅ Passwords are hashed (PBKDF2, 600K iterations)
✅ Email is unique
✅ Phone numbers validated
✅ OneToOne prevents duplicates
✅ Admin-only operations protected
✅ Auto-sync between profiles and BaseUser
✅ CASCADE delete prevents orphans

---

## 📂 File Quick Guide

| Need | Read |
|------|------|
| Understand system | `AUTHENTICATION_ARCHITECTURE.md` |
| Setup database | `MIGRATION_DEPLOYMENT.md` |
| Copy-paste code | `CODE_EXAMPLES.md` |
| Visual diagrams | `ARCHITECTURE_DIAGRAMS.md` |
| Full checklist | `SETUP_VERIFICATION.md` |
| Implementation summary | `README_IMPLEMENTATION.md` |

---

## 🚀 Common Implementation Tasks

### 1. Create Registration View
```python
# views.py
def register_client(request):
    if request.method == 'POST':
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = ClientRegistrationForm()
    return render(request, 'register.html', {'form': form})
```

### 2. Create Login View
```python
from django.contrib.auth import authenticate, login

def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect_by_role(user)
    return render(request, 'login.html')
```

### 3. Protect Dashboard
```python
from django.contrib.auth.decorators import login_required

@login_required
def client_dashboard(request):
    profile = request.user.client_profile
    return render(request, 'dashboard.html', {'profile': profile})
```

### 4. Verify Lawyer (Admin View)
```python
def verify_lawyer(request, lawyer_id):
    lawyer = LawyerProfile.objects.get(id=lawyer_id)
    lawyer.verified = True
    lawyer.save()
    return redirect('admin:lawyers_lawyerprofile_change', lawyer_id)
```

### 5. Activate Admin (Superuser View)
```python
def activate_admin(request, admin_id):
    admin = AdminPanelProfile.objects.get(id=admin_id)
    admin.is_verified_by_superuser = True
    admin.save()  # Auto-syncs to BaseUser.is_staff & is_active
    return redirect('admin:adminpanel_adminpanelprofile_change', admin_id)
```

---

## 🐛 Quick Debugging

### Can't Login
```python
# Check if user exists
BaseUser.objects.filter(email='user@example.com').exists()

# Check password
user = BaseUser.objects.get(email='user@example.com')
user.check_password('password')  # Returns True/False
```

### Profile Not Created
```python
# Check if profile exists
user = BaseUser.objects.get(email='user@example.com')
hasattr(user, 'client_profile')  # Should be True after registration
```

### Admin Not Activated
```python
# Check verification status
admin = AdminPanelProfile.objects.first()
admin.is_verified_by_superuser  # Should be True
admin.user.is_staff              # Should auto-sync to True
admin.user.is_active             # Should auto-sync to True
```

---

## 🎨 Model Fields Reference

### Gender Choices
```python
('male', 'Male'), ('female', 'Female'), ('other', 'Other')
```

### Marital Status (Clients)
```python
('single', 'Single'), ('married', 'Married'), ('divorced', 'Divorced'),
('widowed', 'Widowed'), ('separated', 'Separated')
```

### Specialization (Lawyers)
```python
('criminal', 'Criminal Law'), ('family', 'Family Law'), 
('corporate', 'Corporate Law'), ('ip', 'Intellectual Property'),
('labor', 'Labor Law'), ('tax', 'Tax Law'),
('real_estate', 'Real Estate'), ('bankruptcy', 'Bankruptcy Law'),
('other', 'Other')
```

---

## 📊 Data Model Summary

```
BaseUser (Auth)
├─ id, email (unique), password (hashed)
├─ first_name, last_name, is_active, is_staff
└─ created_at, updated_at

ClientProfile (1:1 with BaseUser)
├─ first_name, last_name, gender, date_of_birth
├─ marital_status, mobile_number
└─ date_of_join

LawyerProfile (1:1 with BaseUser)
├─ full_name, gender, date_of_birth
├─ bar_registration_number (unique), years_of_experience
├─ specialization, rating (0-5), verified
└─ date_joined

AdminPanelProfile (1:1 with BaseUser)
├─ full_name, gender, date_of_birth
├─ mobile_number
├─ is_verified_by_superuser (syncs to user.is_staff & is_active)
└─ date_of_join
```

---

## ✅ Verification Commands

```bash
# 1. Check models
python manage.py sqlmigrate accounts 0001

# 2. Check migrations applied
python manage.py showmigrations

# 3. Count users
python manage.py shell
>>> from accounts.models import BaseUser
>>> BaseUser.objects.count()

# 4. Verify admin access
# Login at http://localhost:8000/admin
```

---

## 🔄 Common Patterns

### Create User Programmatically
```python
from accounts.models import BaseUser
user = BaseUser.objects.create_user(
    email='user@example.com',
    password='SecurePass123'
)
```

### Update User Password
```python
user = BaseUser.objects.get(email='user@example.com')
user.set_password('NewPassword123')
user.save()
```

### Deactivate User
```python
user = BaseUser.objects.get(email='user@example.com')
user.is_active = False
user.save()
```

### Query by Profile Data
```python
# Find married clients
from clients.models import ClientProfile, MaritalStatus
married = ClientProfile.objects.filter(marital_status=MaritalStatus.MARRIED)

# Find top lawyers
lawyers = LawyerProfile.objects.filter(verified=True).order_by('-rating')[:5]

# Find unverified admins
admins = AdminPanelProfile.objects.filter(is_verified_by_superuser=False)
```

---

## 📞 When Things Go Wrong

| Error | Solution |
|-------|----------|
| AUTH_USER_MODEL not installed | Add accounts to INSTALLED_APPS first |
| Table doesn't exist | Run `python manage.py migrate` |
| Email not unique | Check model has unique=True |
| Password mismatch error | Form is validating correctly ✓ |
| Profile not found | Use .get() instead of direct access |
| Can't verify lawyer | Use Django admin or implement verify view |

---

## 🎓 Next: Build Your Views!

Now that models/forms are ready:

1. Create `accounts/urls.py` with register/login URLs
2. Create registration templates
3. Create dashboard templates
4. Add email verification (optional)
5. Add password reset (optional)

See `CODE_EXAMPLES.md` for complete view examples.

---

**Quick Reference Version**: 1.0
**Last Updated**: 2024-06-22
