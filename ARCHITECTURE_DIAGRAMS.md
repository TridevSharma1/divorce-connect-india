# System Architecture Diagrams

## Database Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BaseUser (accounts)                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ PK: id (auto)                                               │  │
│  │ email (unique, CharField 254) ← USERNAME_FIELD             │  │
│  │ password (hashed)                                           │  │
│  │ first_name, last_name                                       │  │
│  │ is_active, is_staff, is_superuser                          │  │
│  │ created_at, updated_at (timestamps)                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────┬──────────────────────────┬──────────────────────────┬───┘
           │ (OneToOne)               │ (OneToOne)               │ (OneToOne)
           │                          │                          │
           ▼                          ▼                          ▼
    ┌────────────────┐        ┌────────────────┐       ┌─────────────────┐
    │ ClientProfile  │        │ LawyerProfile  │       │AdminPanelProfile│
    ├────────────────┤        ├────────────────┤       ├─────────────────┤
    │ user: FK▲      │        │ user: FK▲      │       │ user: FK▲       │
    │ first_name     │        │ full_name      │       │ full_name       │
    │ last_name      │        │ gender         │       │ gender          │
    │ gender         │        │ date_of_birth  │       │ date_of_birth   │
    │ date_of_birth  │        │ bar_reg_number │       │ mobile_number   │
    │ marital_status │        │ state_bar      │       │ alt_mobile      │
    │ mobile_number  │        │ years_exp      │       │ is_verified_by  │
    │ alt_mobile     │        │ specialization │       │ superuser       │
    │ date_of_join   │        │ rating (0-5)   │       │ date_of_join    │
    │ updated_at     │        │ verified       │       │ updated_at      │
    │                │        │ mobile_number  │       │                 │
    │ Methods:       │        │ alt_mobile     │       │ Custom save():  │
    │ get_full_name()│        │ date_joined    │       │ Syncs to:       │
    │                │        │ updated_at     │       │ user.is_staff   │
    │ Indexes:       │        │ Methods:       │       │ user.is_active  │
    │ date_of_join   │        │ (none)         │       │                 │
    │                │        │ Indexes:       │       │ Indexes:        │
    │ Validators:    │        │ [verified,     │       │ (none)          │
    │ phone_regex    │        │  -rating]      │       │                 │
    │                │        │ [specializ]    │       │ Validators:     │
    │ Choices:       │        │                │       │ phone_regex     │
    │ Gender:        │        │ Validators:    │       │                 │
    │ - male         │        │ phone_regex    │       │ Permissions:    │
    │ - female       │        │ bar_reg unique │       │ Superuser only  │
    │ - other        │        │                │       │ (enforced in    │
    │                │        │ Choices:       │       │  admin.py)      │
    │ MaritalStatus: │        │ Gender: (same) │       │                 │
    │ - single       │        │ Specialization:│       │                 │
    │ - married      │        │ - criminal     │       │                 │
    │ - divorced     │        │ - family       │       │                 │
    │ - widowed      │        │ - corporate    │       │                 │
    │ - separated    │        │ - ip           │       │                 │
    │                │        │ - labor        │       │                 │
    │ Related name:  │        │ - tax          │       │ Related name:   │
    │ client_profile │        │ - real_estate  │       │ admin_profile   │
    │                │        │ - bankruptcy   │       │                 │
    │                │        │ - other        │       │                 │
    │                │        │                │       │                 │
    │                │        │ Related name:  │       │                 │
    │                │        │ lawyer_profile │       │                 │
    └────────────────┘        └────────────────┘       └─────────────────┘
```

## Authentication Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        LOGIN FLOW                                        │
└──────────────────────────────────────────────────────────────────────────┘

User enters credentials
        │
        ▼
┌─────────────────────────┐
│ Email: user@example.com │
│ Password: ••••••••••••  │
└─────────────────────────┘
        │
        ▼
Form Validation
        │
        ├─────────────────────────────────────────┐
        │                                         │
        ▼                                         ▼
  Valid?                                    Invalid ─► Show errors
  (Yes)                                              (Retry)
        │
        ▼
authenticate(username=email, password=password)
        │
        ├─ Find BaseUser by email (USERNAME_FIELD='email')
        │
        ├─ Verify password hash match
        │
        ├─────────────────────────────────┐
        │                                 │
        ▼                                 ▼
      Match?                          No match ─► Return None
      (Yes)                                      (Error)
        │
        ▼
Check user.is_active
        │
        ├─────────────────────────────────┐
        │                                 │
        ▼                                 ▼
      True?                           False ─► Error
      (Yes)                                   (Account disabled)
        │
        ▼
login(request, user)
        │
        ├─ Create session
        ├─ Set cookies
        │
        ▼
Check user type
        │
    ┌───┴────┬──────────┐
    │        │          │
    ▼        ▼          ▼
  Client  Lawyer     Admin
    │        │          │
    ▼        ▼          ▼
Redirect to appropriate dashboard
```

## Registration Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   CLIENT REGISTRATION FLOW                               │
└──────────────────────────────────────────────────────────────────────────┘

User fills form:
┌────────────────────────────────────┐
│ Email:                             │
│ Password1:                         │
│ Password2:                         │
│ First Name:                        │
│ Last Name:                         │
│ Gender:                            │
│ Date of Birth:                     │
│ Marital Status:                    │
│ Mobile Number:                     │
│ Alternate Mobile:                  │
└────────────────────────────────────┘
         │
         ▼
ClientRegistrationForm.clean()
         │
    ┌────┴────┬──────┬─────────────┐
    │         │      │             │
    ▼         ▼      ▼             ▼
  Email    Password Phone    Other
  unique?  match?   format?  valid?
    │         │      │        │
    └─────┬───┴──────┴────────┘
          │
          ├─────────────────────┐
          │                     │
          ▼                     ▼
       Valid?               Invalid
       (Yes)                (No)
         │                   │
         ▼                   ▼
    form.save()        Show errors
         │             (Retry)
    ┌────┴──────────────────────────┐
    │                               │
    ▼                               ▼
Create BaseUser               (User fills again)
    │
    ├─ Set email as username
    ├─ Hash password using PBKDF2
    ├─ Save to DB
    │
    ▼
Create ClientProfile
    │
    ├─ Link to BaseUser (OneToOne)
    ├─ Save all profile data
    │
    ▼
login(request, user)
    │
    ├─ Create session
    │
    ▼
Redirect to dashboard
```

## Form Validation Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                   FORM VALIDATION LAYERS                        │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  Model Field Level (Database Constraints) │
├───────────────────────────────────────────┤
│ • email: unique=True, max_length=254      │
│ • phone: RegexValidator pattern           │
│ • bar_number: unique=True (Lawyer)        │
│ • rating: MinValidator(0), MaxValidator(5)│
└───────────────────────────────────────────┘
         ▲
         │
┌────────┴──────────────────────────────────┐
│    Form Field Level (Form Validation)     │
├────────────────────────────────────────────┤
│ • clean_email(): Check uniqueness         │
│ • clean_password2(): Match check          │
│ • clean_bar_registration_number():        │
│   Check uniqueness for Lawyer             │
└────────────────────────────────────────────┘
         ▲
         │
┌────────┴──────────────────────────────────┐
│  Widget Level (HTML5 & Client-side)       │
├────────────────────────────────────────────┤
│ • EmailInput: HTML5 email validation      │
│ • PasswordInput: type="password"          │
│ • DateInput: type="date"                  │
│ • Select: Dropdown for choices            │
└────────────────────────────────────────────┘
```

## Admin Panel Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                      Django Admin                       │
│                   (/admin)                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ACCOUNTS                                         │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • Base Users                                     │  │
│  │   ├─ List by email, is_staff, is_active        │  │
│  │   ├─ Filter by created_at, permissions         │  │
│  │   └─ Search by email, name                      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ CLIENTS                                          │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • Client Profiles                                │  │
│  │   ├─ List with email, phone, marital status     │  │
│  │   ├─ Filter by gender, marital_status, date     │  │
│  │   └─ Search by name, email, phone               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ LAWYERS                                          │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • Lawyer Profiles                                │  │
│  │   ├─ List with specialization, rating, verified │  │
│  │   ├─ Filter by specialization, verified, rating │  │
│  │   ├─ Search by name, email, bar number          │  │
│  │   └─ Actions: Mark Verified, Mark Unverified    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ADMINPANEL                                       │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • Admin Panel Profiles [SUPERUSER ONLY]          │  │
│  │   ├─ List with verification status               │  │
│  │   ├─ Filter by verification status, date         │  │
│  │   ├─ Search by name, email                       │  │
│  │   ├─ Actions: Verify, Unverify                   │  │
│  │   └─ Permissions: Add, Change, Delete for Admins │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Password Security Flow

```
┌──────────────────────────────────────────────────────────────┐
│                   PASSWORD HANDLING                         │
└──────────────────────────────────────────────────────────────┘

REGISTRATION:
        │
        ▼
User enters: password="SecurePass123", confirm="SecurePass123"
        │
        ▼
Form Level:
    • password1 and password2 are form fields only
    • NOT model fields
    • Validated to match
        │
        ▼
form.save():
    • Calls User.set_password("SecurePass123")
    • Django hashes using PBKDF2:
      "pbkdf2_sha256$600000$abc123xyz$..."
    • Stored in BaseUser.password (irreversible)
        │
        ▼
DATABASE:
    BaseUser.password = "pbkdf2_sha256$600000$..."


LOGIN:
        │
        ▼
User enters: email="user@example.com", password="SecurePass123"
        │
        ▼
authenticate():
    • Finds BaseUser by email
    • Calls check_password("SecurePass123")
    • Django rehashes and compares
        │
        ├─────────────────────────────┐
        │                             │
        ▼                             ▼
    Match?                        No Match
    (Yes)                         (Error)
        │
        ▼
Return BaseUser instance


VALIDATION RULES (Django Defaults):
    ✓ Minimum 8 characters
    ✓ Not common password (rockyou.txt)
    ✓ Not similar to email/name
    ✓ Not all numeric
    ✓ Custom validators can be added
```

## Data Flow: From User to Database

```
User Input Form
    │
    ▼
┌──────────────────────────┐
│ Form Validation Layer    │
├──────────────────────────┤
│ • Field clean methods    │
│ • Form clean method      │
│ • Custom validators      │
│ • Constraint checks      │
└──────────────────────────┘
    │ (Valid only)
    ▼
┌──────────────────────────┐
│ Form Save Logic          │
├──────────────────────────┤
│ • cleaned_data dict      │
│ • Model instance created │
│ • Password hashed        │
│ • OneToOne relations set │
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│ Model Pre-Save Signals   │
├──────────────────────────┤
│ • Custom logic in save() │
│ • For AdminProfile:      │
│   └─ Sync to BaseUser    │
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│ Django ORM               │
├──────────────────────────┤
│ • SQL generation         │
│ • Database constraints   │
│ • Transaction handling   │
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│ Database                 │
├──────────────────────────┤
│ • Models stored          │
│ • Relations maintained   │
│ • Data persisted         │
└──────────────────────────┘
```

## User Type Detection Logic

```
┌─────────────────────────────────────────────────────┐
│  def get_user_role(user):                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  if hasattr(user, 'client_profile'):               │
│      return 'CLIENT'                               │
│      └─ user.client_profile accessible             │
│                                                     │
│  elif hasattr(user, 'lawyer_profile'):             │
│      return 'LAWYER'                               │
│      └─ user.lawyer_profile accessible             │
│                                                     │
│  elif hasattr(user, 'admin_profile'):              │
│      return 'ADMIN'                                │
│      └─ user.admin_profile accessible              │
│                                                     │
│  return None                                        │
│                                                     │
└─────────────────────────────────────────────────────┘

This works because:
• OneToOneField creates a related_name
• related_name: 'client_profile', 'lawyer_profile', 'admin_profile'
• Each user has at most ONE related profile
• hasattr() checks if the related object exists
```

## Permission & Verification Model

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT                                   │
├─────────────────────────────────────────────────────────────┤
│ BaseUser.is_active = True (default from register)           │
│ BaseUser.is_staff = False                                   │
│ Status: Ready to use immediately                            │
│ Access: Dashboard available                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    LAWYER                                   │
├─────────────────────────────────────────────────────────────┤
│ BaseUser.is_active = True (default from register)           │
│ BaseUser.is_staff = False                                   │
│ LawyerProfile.verified = False (admin must verify)          │
│ Status: Waiting for admin verification                      │
│ Access: Limited dashboard (not verified)                    │
└─────────────────────────────────────────────────────────────┘
         │
         │ (Admin verifies: LawyerProfile.verified = True)
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAWYER (VERIFIED)                        │
├─────────────────────────────────────────────────────────────┤
│ BaseUser.is_active = True                                   │
│ BaseUser.is_staff = False                                   │
│ LawyerProfile.verified = True                               │
│ Status: Active and verified                                 │
│ Access: Full dashboard                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    ADMIN                                    │
├─────────────────────────────────────────────────────────────┤
│ BaseUser.is_active = False (initially)                      │
│ BaseUser.is_staff = False (initially)                       │
│ AdminPanelProfile.is_verified_by_superuser = False          │
│ Status: Created but not activated                           │
│ Access: NO access (not staff, not active)                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ (Superuser verifies: AdminPanelProfile.is_verified = True)
         │ (Triggers: save() which sets is_staff=True, is_active=True)
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    ADMIN (VERIFIED)                         │
├─────────────────────────────────────────────────────────────┤
│ BaseUser.is_active = True (auto-synced)                     │
│ BaseUser.is_staff = True (auto-synced)                      │
│ AdminPanelProfile.is_verified_by_superuser = True           │
│ Status: Active and verified                                 │
│ Access: Admin panel access                                  │
└─────────────────────────────────────────────────────────────┘
```

---

**Diagrams Version**: 1.0
**Last Updated**: 2024-06-22
