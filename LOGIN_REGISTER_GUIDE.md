# DivorceConnect - Login & Register Flow Guide

## 🎯 Quick Access URLs

### Authentication Pages
- **Login:** `http://localhost:8000/api/auth/login/`
- **Register:** `http://localhost:8000/api/auth/register/`
- **Logout:** `http://localhost:8000/api/auth/logout/`

### Role-Specific Dashboards
- **Client Dashboard:** `http://localhost:8000/clients/dashboard/`
- **Lawyer Dashboard:** `http://localhost:8000/lawyers/dashboard/`
- **Admin Dashboard:** `http://localhost:8000/adminpanel/dashboard/`

---

## 📊 Registration Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   REGISTRATION PAGE                         │
│          /api/auth/register/                                │
│                                                             │
│  1. Select Role: [◉ Client] [ ] Lawyer [ ] Admin          │
│  2. First Name: [________]                                 │
│  3. Last Name: [________]                                  │
│  4. Email: [________@example.com]                          │
│  5. Password: [________] (min 8 chars)                     │
│  6. Confirm Password: [________]                           │
│  7. [Create Account Button]                                │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  Validate All Fields         │
            │  • Email unique?             │
            │  • Passwords match?          │
            │  • Min 8 characters?         │
            │  • All required?             │
            └──────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────────┐
            │  Create BaseUser Instance        │
            │  + Email                         │
            │  + Password (hashed)             │
            │  + First/Last Name               │
            └──────────────────────────────────┘
                           │
                           ▼
        ┌───────────────────────────────────────────┐
        │  Create Role-Specific Profile             │
        ├───────────────────────────────────────────┤
        │ IF role == 'client':                      │
        │   → ClientProfile                         │
        │                                           │
        │ ELIF role == 'lawyer':                    │
        │   → LawyerProfile                         │
        │      (auto-fill license #, state, etc)    │
        │                                           │
        │ ELIF role == 'admin':                     │
        │   → AdminPanelProfile                     │
        └───────────────────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  Auto-Login User             │
            │  Set Session Cookie          │
            └──────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │  Redirect to Dashboard                   │
        ├──────────────────────────────────────────┤
        │ IF client_profile exists:                │
        │   → /clients/dashboard/                  │
        │                                          │
        │ ELIF lawyer_profile exists:              │
        │   → /lawyers/dashboard/                  │
        │                                          │
        │ ELIF admin_profile exists:               │
        │   → /adminpanel/dashboard/               │
        └──────────────────────────────────────────┘
```

---

## 🔐 Login Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   LOGIN PAGE                            │
│          /api/auth/login/                               │
│                                                         │
│  Email: [user@example.com]                              │
│  Password: [••••••••]                                   │
│  [ ] Remember Me                                        │
│  [Sign In Button]                                       │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  Authenticate User           │
        │  • Check email exists        │
        │  • Verify password           │
        └──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
    ✅ Valid                      ❌ Invalid
        │                             │
        ▼                             ▼
   Auto-Login            Show Error Message
   Set Session           Clear Form
        │
        ▼
┌──────────────────────────────────────┐
│  Check User Role via hasattr()       │
├──────────────────────────────────────┤
│ IF user.client_profile exists:       │
│   → /clients/dashboard/              │
│                                      │
│ ELIF user.lawyer_profile exists:     │
│   → /lawyers/dashboard/              │
│                                      │
│ ELIF user.admin_profile exists:      │
│   → /adminpanel/dashboard/           │
└──────────────────────────────────────┘
```

---

## 👥 Client Navbar & Dashboard

### Navbar Links
```
[Logo] | Home | Lawyer Section | Counseling | About | Support | Contact | 🔔 | [👤 ▼]
```

### Profile Dropdown Menu
```
┌─────────────────────────────────┐
│ • My Case Status                │
│ • Support                       │
│ • Profile                       │
│ • Report Lawyer                 │
│ ─────────────────────────────── │
│ • Logout                        │
└─────────────────────────────────┘
```

### Dashboard Content
```
┌────────────────────────────────────────────────────────────────┐
│                  Welcome, John Doe                             │
│              Manage your legal matters with confidence          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ Find Lawyer │  │ Counseling  │  │ My Cases    │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ About       │  │ Support     │  │ Contact     │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## ⚖️ Lawyer Navbar & Dashboard

### Navbar Links
```
[Logo] | Home | Earning Dashboard | Case Order | Case Status | Account Settings | Billing & Payment | Profile | 🔔 | [👤 ▼]
```

### Profile Dropdown Menu
```
┌─────────────────────────────────┐
│ • My Case Order                 │
│ • Support                       │
│ • Profile                       │
│ • Report Client                 │
│ ─────────────────────────────── │
│ • Logout                        │
└─────────────────────────────────┘
```

### Dashboard Content
```
┌────────────────────────────────────────────────────────────────┐
│                  Welcome back, Jane Smith                      │
│                    Your practice dashboard                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │Total Cases   │ │Yearly Earn   │ │Monthly Earn  │          │
│  │     24       │ │   ₹4.2L      │ │    ₹35K      │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
│                                                                │
│  ┌──────────────┐                                             │
│  │Pending Cases │                                             │
│  │      5       │                                             │
│  └──────────────┘                                             │
│                                                                │
│  ┌────────────────────────┐ ┌──────────────────┐             │
│  │  Case Requests (3)     │ │  Recent Clients  │             │
│  ├────────────────────────┤ ├──────────────────┤             │
│  │ • Divorce Settlement   │ │ • Priya Singh    │             │
│  │ • Custody Matter       │ │ • Rajesh Kumar   │             │
│  │ • Documentation Review │ │ • Anjali Patel   │             │
│  └────────────────────────┘ │ • Vikram Sharma  │             │
│                             └──────────────────┘             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Admin Navbar & Dashboard

### Navbar Links
```
[Logo] | Home | Verify Documents | Verify Lawyer | Request Counseling | Report | 🔔 | [👤 ▼]
```

### Profile Dropdown Menu
```
┌─────────────────────────────────┐
│ • Support                       │
│ • Profile                       │
│ • Report Issue                  │
│ ─────────────────────────────── │
│ • Logout                        │
└─────────────────────────────────┘
```

### Dashboard Content
```
┌────────────────────────────────────────────────────────────────┐
│                    Admin Dashboard                             │
│                  Platform management and monitoring            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────┐ ┌────────────┐ ┌──────────────┐         │
│  │ Pending Verif   │ │Active Cases│ │Disputes      │         │
│  │      12         │ │    156     │ │     8        │         │
│  └─────────────────┘ └────────────┘ └──────────────┘         │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Lawyer Verification Queue                              │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ • Dr. Rajesh Kumar      [Pending]                       │   │
│  │ • Priya Sharma          [Under Review]                  │   │
│  │ • Vikram Patel          [Action Needed]                 │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Document Verification                                  │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ • Identity Proof        [Pending]                       │   │
│  │ • Legal License         [Under Review]                  │   │
│  │ • Bar License           [Verified]                      │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Session Management

### On Login/Register
- User session is created
- Django session cookie is set
- User is authenticated in the request context

### On Logout
- Session is cleared
- Cookie is deleted
- User is redirected to home page

### Protected Routes
- All dashboard routes require `@login_required` decorator
- Additionally check for role-specific profile
- Redirects to login if not authenticated

---

## ✅ What Works

✅ User can register with email-based account
✅ User selects role during registration
✅ Role-specific profile is created automatically
✅ User is logged in after registration
✅ User is redirected to appropriate dashboard based on role
✅ Login validates email and password
✅ Login redirects to appropriate dashboard based on role
✅ Logout clears session and redirects to home
✅ Password validation (min 8 characters)
✅ Email uniqueness check
✅ Password confirmation match
✅ Error messages displayed on forms
✅ Mobile responsive design
✅ CSRF protection on all forms

---

## 🧪 Quick Test Checklist

- [ ] Register as Client and verify redirect to `/clients/dashboard/`
- [ ] Register as Lawyer and verify redirect to `/lawyers/dashboard/`
- [ ] Register as Admin and verify redirect to `/adminpanel/dashboard/`
- [ ] Login with existing client account and verify dashboard
- [ ] Login with existing lawyer account and verify dashboard
- [ ] Login with existing admin account and verify dashboard
- [ ] Test logout from each role
- [ ] Verify error message for invalid login credentials
- [ ] Verify error message for password mismatch in registration
- [ ] Verify error message for duplicate email
- [ ] Test mobile navbar toggle
- [ ] Test profile dropdown menus
- [ ] Verify cannot access dashboard without login
