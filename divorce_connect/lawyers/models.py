from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from accounts.models import BaseUser


class Specialization(models.TextChoices):
    """Legal specialization choices for lawyers."""
    CRIMINAL = "criminal", "Criminal Law"
    FAMILY = "family", "Family Law"
    CORPORATE = "corporate", "Corporate Law"
    INTELLECTUAL_PROPERTY = "ip", "Intellectual Property"
    LABOR = "labor", "Labor Law"
    TAX = "tax", "Tax Law"
    REAL_ESTATE = "real_estate", "Real Estate"
    BANKRUPTCY = "bankruptcy", "Bankruptcy Law"
    OTHER = "other", "Other"

# --- Put this at the top, above your models ---

class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"

# NEW: Global Validator
indian_phone_validator = RegexValidator(
    regex=r'^(\+91|0)?[6-9]\d{9}$',
    message="Phone number must be in Indian format (10 digits starting with 6-9, or +91..."
)


class LawyerProfile(models.Model):
    """
    Lawyer user profile linked to BaseUser via OneToOneField.
    Extends authentication capabilities with lawyer-specific professional information.
    """

    # Link to BaseUser (one-to-one relationship)
    user = models.OneToOneField(
        BaseUser,
        on_delete=models.CASCADE,
        related_name='lawyer_profile',
        help_text="Associated BaseUser account"
    )

    # Personal Information
    full_name = models.CharField(
        max_length=100,
        help_text="Lawyer's full name"
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.OTHER,
        help_text="Lawyer's gender"
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Lawyer's date of birth"
    )

    # Professional Information
    bar_registration_number = models.CharField(
        max_length=50,
        unique=True,
        blank=False,
        help_text="Bar council registration/license number - Must be entered by user"
    )

    state_bar_council = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the state bar council where registered"
    )

    years_of_experience = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        default=0,
        help_text="Number of years of legal practice experience"
    )

    specialization = models.CharField(
        max_length=50,
        choices=Specialization.choices,
        default=Specialization.OTHER,
        help_text="Primary area of legal specialization"
    )

    # Professional Profile Details
    bio = models.TextField(
        blank=True,
        max_length=500,
        help_text="Professional biography and background"
    )

    consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Hourly consultation fee in rupees"
    )

    office_city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City where the lawyer's office is located"
    )

    # Ratings and Verification
    rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        help_text="Professional rating (0.0 to 5.0 scale)"
    )

    verified = models.BooleanField(
        default=False,
        help_text="Is the lawyer's credentials verified by admin?"
    )

    # Contact Information

    mobile_number = models.CharField(
        max_length=13,
        validators=[indian_phone_validator],
        blank=True,
        help_text="Lawyer's primary mobile number (10 digits)"
    )

    alternate_mobile_number = models.CharField(
        max_length=13,
        validators=[indian_phone_validator],
        blank=True,
        null=True,
        help_text="Lawyer's alternate mobile number (optional)"
    )

    # Profile Picture
    profile_picture = models.ImageField(
        upload_to='lawyer_pictures/',
        null=True,
        blank=True,
        help_text="Lawyer's profile picture"
    )

    # Profile Completion & Verification Status
    is_profile_complete = models.BooleanField(
        default=False,
        help_text="Has lawyer completed their profile and submitted for verification?"
    )

    # Timestamps
    date_joined = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when lawyer joined the platform"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag for a lawyer profile"
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the lawyer profile was soft deleted"
    )

    class Meta:
        verbose_name = "Lawyer Profile"
        verbose_name_plural = "Lawyer Profiles"
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['verified', '-rating']),
            models.Index(fields=['specialization']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.user.email})"

    @property
    def report_count(self):
        """Return the number of reports filed against this lawyer."""
        return self.received_reports.count()

    @property
    def is_ban_eligible(self):
        """Return True when the lawyer has reached ban eligibility threshold."""
        return self.report_count >= 3

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.user.is_active = False
        self.user.is_staff = False
        self.user.save(update_fields=['is_active', 'is_staff'])
        self.save(update_fields=['is_deleted', 'deleted_at'])


class DeletedLawyerProfile(LawyerProfile):
    class Meta:
        proxy = True
        verbose_name = 'Deleted Lawyer Profile'
        verbose_name_plural = 'Deleted Lawyer Profiles'


class CaseRequest(models.Model):
    """Represents a client request to hire a lawyer."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('DOCUMENTS_PENDING', 'Waiting for Documents'),
        ('DOCUMENTS_SUBMITTED', 'Documents Submitted'),
        ('DOCUMENTS_VERIFIED', 'Documents Verified'),
        ('ACCEPTED', 'Accepted'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]

    client = models.ForeignKey(
        'clients.ClientProfile',
        on_delete=models.CASCADE,
        related_name='sent_case_requests',
        help_text='Client who sent this request'
    )
    lawyer = models.ForeignKey(
        LawyerProfile,
        on_delete=models.CASCADE,
        related_name='case_requests',
        help_text='Lawyer who is requested'
    )
    message = models.TextField(blank=True, help_text='Client message or summary of the request')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    response_message = models.TextField(blank=True, null=True, help_text='Optional lawyer response message')
    documents_submitted_at = models.DateTimeField(null=True, blank=True, help_text='When documents were submitted')
    documents_verified_at = models.DateTimeField(null=True, blank=True, help_text='When documents were verified by admin')

    WORKFLOW_STAGES = [
        ('CASE_CREATED', 'Case Created'),
        ('DOCUMENT_VERIFICATION', 'Document Verification'),
        ('LAWYER_ASSIGNED', 'Lawyer Assigned'),
        ('PETITION_DRAFTED', 'Petition Drafted'),
        ('PETITION_FILED', 'Petition Filed'),
        ('FIRST_MOTION', 'First Motion'),
        ('SECOND_MOTION', 'Second Motion'),
        ('DECREE_ISSUED', 'Decree Issued'),
        ('COMPLETED', 'Completed'),
    ]

    workflow_stage = models.CharField(
        max_length=30,
        choices=WORKFLOW_STAGES,
        default='CASE_CREATED',
        help_text='Latest completed workflow milestone for the case'
    )
    workflow_stage_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the workflow stage was last updated'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Case Request'
        verbose_name_plural = 'Case Requests'

    def __str__(self):
        return f"Case request from {self.client.get_full_name()} to {self.lawyer.full_name} ({self.status})"

    @property
    def is_documents_verified(self):
        """Check if all documents are verified"""
        return self.status == 'DOCUMENTS_VERIFIED'

    @property
    def documents_pending_count(self):
        """Get count of pending documents"""
        return self.case_documents.filter(
            casedocumentverification__status='PENDING'
        ).count()

    @property
    def documents_verified_count(self):
        """Get count of verified documents"""
        return self.case_documents.filter(
            casedocumentverification__status='VERIFIED'
        ).count()

    @property
    def documents_rejected_count(self):
        """Get count of rejected documents"""
        return self.case_documents.filter(
            casedocumentverification__status='REJECTED'
        ).count()

    @property
    def total_documents_count(self):
        """Get total count of documents for this case"""
        return self.case_documents.count()

    @property
    def all_documents_verified(self):
        """Check if all documents are verified (no pending or rejected)"""
        if self.total_documents_count == 0:
            return False
        return self.documents_verified_count == self.total_documents_count

    @property
    def all_documents_reviewed(self):
        """Check if all documents have been reviewed (verified or rejected, no pending)"""
        if self.total_documents_count == 0:
            return False
        pending = self.documents_pending_count
        return pending == 0

    @property
    def workflow_stage_order(self):
        return [stage[0] for stage in self.WORKFLOW_STAGES]

    @property
    def next_workflow_stage(self):
        order = self.workflow_stage_order
        try:
            current_index = order.index(self.workflow_stage)
        except ValueError:
            return None
        return order[current_index + 1] if current_index + 1 < len(order) else None

    @property
    def get_next_workflow_stage_display(self):
        next_stage = self.next_workflow_stage
        return dict(self.WORKFLOW_STAGES).get(next_stage)

    @property
    def get_workflow_stage_display(self):
        return dict(self.WORKFLOW_STAGES).get(self.workflow_stage, self.workflow_stage)

    @property
    def workflow_progress(self):
        order = self.workflow_stage_order
        try:
            current_index = order.index(self.workflow_stage)
        except ValueError:
            current_index = 0

        progress = []
        for index, (key, label) in enumerate(self.WORKFLOW_STAGES):
            progress.append({
                'key': key,
                'label': label,
                'completed': index <= current_index,
                'active': index == current_index,
            })
        return progress


class CaseDocument(models.Model):
    """Store documents uploaded by clients for a case."""

    DOCUMENT_TYPES = [
        ('aadhaar', 'Aadhaar Card'),
        ('pan', 'PAN Card'),
        ('marriage_cert', 'Marriage Certificate'),
        ('address_proof', 'Address Proof'),
        ('income_proof', 'Income Proof'),
        ('passport', 'Passport'),
        ('affidavit', 'Affidavits'),
    ]

    case_request = models.ForeignKey(
        CaseRequest,
        on_delete=models.CASCADE,
        related_name='case_documents',
        help_text='Associated case request'
    )

    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        help_text='Type of document'
    )

    document_file = models.FileField(
        upload_to='case_documents/%Y/%m/%d/',
        help_text='Uploaded document file'
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When document was uploaded'
    )

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Case Document'
        verbose_name_plural = 'Case Documents'
        unique_together = ['case_request', 'document_type']

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.case_request}"

    @property
    def file_extension(self):
        """Get file extension in lowercase."""
        if self.document_file:
            return self.document_file.name.lower().split('.')[-1]
        return ''

    @property
    def is_pdf(self):
        """Check if document is a PDF."""
        return self.file_extension == 'pdf'

    @property
    def is_image(self):
        """Check if document is an image."""
        return self.file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']


class CaseDocumentVerification(models.Model):
    """Track admin verification of case documents."""

    VERIFICATION_STATUS = [
        ('PENDING', 'Pending Review'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]

    document = models.OneToOneField(
        CaseDocument,
        on_delete=models.CASCADE,
        related_name='casedocumentverification',
        help_text='Associated document'
    )

    status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='PENDING',
        help_text='Verification status'
    )

    verified_by = models.ForeignKey(
        BaseUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_case_documents',
        help_text='Admin who verified this document'
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When document was verified'
    )

    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text='Reason for rejection if applicable'
    )

    class Meta:
        ordering = ['-verified_at']
        verbose_name = 'Case Document Verification'
        verbose_name_plural = 'Case Document Verifications'

    def __str__(self):
        return f"Verification of {self.document.get_document_type_display()} - {self.status}"


class LawyerProfileUpdateRequest(models.Model):
    """Holds profile edits waiting for Admin approval."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    lawyer = models.ForeignKey('LawyerProfile', on_delete=models.CASCADE, related_name='update_requests')

    full_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    years_of_experience = models.PositiveIntegerField(null=True, blank=True)
    specialization = models.CharField(max_length=50, choices=Specialization.choices, blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    office_city = models.CharField(max_length=100, blank=True, null=True)

    mobile_number = models.CharField(max_length=13, validators=[indian_phone_validator], blank=True, null=True)
    alternate_mobile_number = models.CharField(max_length=13, validators=[indian_phone_validator], blank=True, null=True)

    profile_picture = models.ImageField(upload_to='lawyer_updates/', blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True, help_text="Reason for rejection, if applicable.")

    def __str__(self):
        return f"Update Request by {self.lawyer.full_name} - {self.status}"
