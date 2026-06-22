# Migration & Deployment Guide

## Pre-Migration Checklist

✅ **Required Configuration** (Must be in `settings.py`):
```python
AUTH_USER_MODEL = 'accounts.BaseUser'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts.apps.AccountsConfig',  # MUST be before other apps
    'clients.apps.ClientsConfig',
    'lawyers.apps.LawyersConfig',
    'adminpanel.apps.AdminpanelConfig',
]
```

✅ **Database**: Should be empty or not previously migrated with different AUTH_USER_MODEL
✅ **All Models**: Already defined in accounts, clients, lawyers, adminpanel apps
✅ **All Forms**: Already defined in each app's forms.py
✅ **All Admin Configs**: Already defined in each app's admin.py

---

## Migration Steps (Fresh Setup)

### Step 1: Create Migrations

```bash
# Create migrations for accounts app (FIRST)
python manage.py makemigrations accounts

# Create migrations for other apps
python manage.py makemigrations clients
python manage.py makemigrations lawyers
python manage.py makemigrations adminpanel

# Verify migrations were created
python manage.py showmigrations
```

**Expected Output**:
```
accounts
 [ ] 0001_initial
clients
 [ ] 0001_initial
lawyers
 [ ] 0001_initial
adminpanel
 [ ] 0001_initial
```

### Step 2: Apply Migrations

```bash
# Apply all migrations
python manage.py migrate

# Verify migrations were applied
python manage.py showmigrations
```

**Expected Output**:
```
accounts
 [X] 0001_initial
clients
 [X] 0001_initial
lawyers
 [X] 0001_initial
adminpanel
 [X] 0001_initial
...
```

### Step 3: Create Superuser

```bash
# Create a superuser account
python manage.py createsuperuser

# Prompts:
# Email address: admin@example.com
# Password: ••••••••
# Password (again): ••••••••
```

### Step 4: Verify Django Admin

```bash
# Start development server
python manage.py runserver

# Visit http://localhost:8000/admin
# Login with superuser credentials

# You should see:
# - BaseUser in Accounts
# - ClientProfile in Clients
# - LawyerProfile in Lawyers
# - AdminPanelProfile in Adminpanel
```

---

## Common Migration Scenarios

### Scenario 1: Adding a New Field to ClientProfile

**Step 1**: Update the model

```python
# clients/models.py
class ClientProfile(models.Model):
    # ... existing fields ...
    
    # NEW FIELD
    profile_picture = models.ImageField(
        upload_to='client_profiles/',
        blank=True,
        null=True
    )
```

**Step 2**: Create and apply migration

```bash
python manage.py makemigrations clients
python manage.py migrate clients
```

### Scenario 2: Changing Field Type

```python
# lawyers/models.py (BEFORE)
years_of_experience = models.PositiveIntegerField()

# lawyers/models.py (AFTER)
years_of_experience = models.FloatField()
```

```bash
# This requires data migration if field has existing values
python manage.py makemigrations lawyers
python manage.py migrate lawyers
```

### Scenario 3: Adding Required Field to Existing Model

```python
# adminpanel/models.py
department = models.CharField(
    max_length=100,
    default='General'  # Provide default for existing records
)
```

```bash
python manage.py makemigrations adminpanel
# Django will ask if you want to provide a default
# Select option 1: Provide a one-off default now
# Enter: General

python manage.py migrate adminpanel
```

---

## Deployment to Production

### Step 1: Pre-Deployment Checks

```bash
# Check for any issues
python manage.py check

# Run tests (if any)
python manage.py test

# Collect static files (if needed)
python manage.py collectstatic --noinput
```

### Step 2: Database Backup (Important!)

```bash
# Backup SQLite (development)
cp db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)

# Or for PostgreSQL
pg_dump -U username database_name > backup.sql

# Or for MySQL
mysqldump -u username -p database_name > backup.sql
```

### Step 3: Apply Migrations

```bash
# On production server
python manage.py migrate --no-input
```

### Step 4: Create Superuser on Production

```bash
# Create admin account
python manage.py createsuperuser
```

### Step 5: Verify Production Setup

```bash
# Check admin panel is accessible
# Visit https://yourdomain.com/admin
# Login with superuser credentials

# Verify models are registered
# You should see all 4 model groups
```

---

## Troubleshooting Migration Issues

### Issue: "django.core.exceptions.ImproperlyConfigured: AUTH_USER_MODEL refers to model that has not been installed"

**Cause**: AUTH_USER_MODEL set but accounts app not in INSTALLED_APPS

**Solution**:
```python
# settings.py
INSTALLED_APPS = [
    'accounts.apps.AccountsConfig',  # Add this line FIRST
    # ... other apps ...
]

AUTH_USER_MODEL = 'accounts.BaseUser'  # Add this line
```

### Issue: "table accounts_baseuser does not exist"

**Cause**: Migrations not applied

**Solution**:
```bash
python manage.py migrate
```

### Issue: "Column does not exist" error

**Cause**: Database schema out of sync with models

**Solution**:
```bash
# Check migration status
python manage.py showmigrations

# Apply pending migrations
python manage.py migrate
```

### Issue: "Conflicting migrations detected"

**Cause**: Multiple migrations trying to modify the same field

**Solution**:
```bash
# Create a new migration combining changes
python manage.py makemigrations --merge

# Review and apply
python manage.py migrate
```

### Issue: "IntegrityError: UNIQUE constraint failed"

**Cause**: Existing data violates new constraints

**Solution**:
1. Create a data migration
2. Write a custom function to handle existing data
3. Apply migration

```bash
python manage.py makemigrations --empty accounts --name fix_unique_constraint
# Edit the created migration file to add custom logic
python manage.py migrate
```

---

## Rollback Procedure

### Rollback Last Migration

```bash
# Show migration history
python manage.py showmigrations

# Rollback to previous migration
python manage.py migrate accounts 0001  # Go back to first migration
python manage.py migrate accounts 0002  # Go to specific migration
```

### Emergency Rollback (If Corrupted)

```bash
# Restore database from backup
cp db.sqlite3.backup db.sqlite3

# Or restore from SQL
psql -U username database_name < backup.sql

# Verify
python manage.py showmigrations
```

---

## Database Optimization

### Add Indexes After Deployment

Indexes are already defined in LawyerProfile:

```python
# lawyers/models.py
indexes = [
    models.Index(fields=['verified', '-rating']),
    models.Index(fields=['specialization']),
]
```

To add more indexes:

```python
# Update model
class LawyerProfile(models.Model):
    # ... fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['verified', '-rating']),
            models.Index(fields=['specialization']),
            models.Index(fields=['years_of_experience']),  # NEW INDEX
        ]

# Create migration
python manage.py makemigrations lawyers
python manage.py migrate lawyers
```

---

## Database Monitoring

### Check Database Size

```bash
# SQLite
ls -lh db.sqlite3

# PostgreSQL
SELECT pg_size_pretty(pg_database_size('database_name'));

# MySQL
SELECT ROUND(SUM(data_free+index_length+data_length)/1024/1024, 2) as size_in_mb 
FROM INFORMATION_SCHEMA.TABLES WHERE table_schema='database_name';
```

### Monitor Growing Tables

```bash
# Django shell
python manage.py shell

# Count records per model
from accounts.models import BaseUser
from clients.models import ClientProfile
from lawyers.models import LawyerProfile
from adminpanel.models import AdminPanelProfile

print(f"BaseUsers: {BaseUser.objects.count()}")
print(f"Clients: {ClientProfile.objects.count()}")
print(f"Lawyers: {LawyerProfile.objects.count()}")
print(f"Admins: {AdminPanelProfile.objects.count()}")
```

---

## Version Control for Migrations

### Important: Commit Migrations to Git

```bash
# ALWAYS commit migrations to version control
git add */migrations/
git commit -m "Add user authentication system migrations"

# Never ignore migrations
# .gitignore should NOT contain: */migrations/
```

### Handling Migration Conflicts

If your team creates conflicting migrations:

```bash
# Show conflicting migrations
python manage.py showmigrations

# Merge conflicts
python manage.py makemigrations --merge

# Review and apply
python manage.py migrate
```

---

## Continuous Integration/Deployment

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.10
    
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Run migrations
      run: python manage.py migrate
    
    - name: Collect static
      run: python manage.py collectstatic --noinput
    
    - name: Run tests
      run: python manage.py test
    
    - name: Deploy to server
      run: ./deploy.sh
```

---

## Database Backup Strategy

### Automated Daily Backups

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
DB_FILE="db.sqlite3"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create daily backup
cp $DB_FILE $BACKUP_DIR/db_$TIMESTAMP.sqlite3

# Keep only last 30 days
find $BACKUP_DIR -name "db_*.sqlite3" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/db_$TIMESTAMP.sqlite3"
```

```bash
# Add to crontab for automatic daily backups
0 2 * * * /path/to/backup.sh  # Run at 2 AM daily
```

---

## Final Verification Checklist

Before going live:

- [ ] ✅ AUTH_USER_MODEL set in settings.py
- [ ] ✅ accounts app first in INSTALLED_APPS
- [ ] ✅ All migrations created
- [ ] ✅ All migrations applied successfully
- [ ] ✅ Superuser account created
- [ ] ✅ Admin panel accessible
- [ ] ✅ All 4 model groups visible in admin
- [ ] ✅ Database backed up
- [ ] ✅ Tests pass
- [ ] ✅ No database integrity errors
- [ ] ✅ Can login with email
- [ ] ✅ Passwords properly hashed
- [ ] ✅ Forms validate correctly

---

## Support Resources

- Django Migrations: https://docs.djangoproject.com/en/6.0/topics/migrations/
- Custom User Model: https://docs.djangoproject.com/en/6.0/topics/auth/customizing/
- Database Router: https://docs.djangoproject.com/en/6.0/topics/db/multi-db/

---

**Version**: 1.0
**Last Updated**: 2024-06-22
**Django Version**: 6.0.3+
