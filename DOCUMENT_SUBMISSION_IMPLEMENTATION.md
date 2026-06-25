# Document Submission System - Implementation Guide

## Overview
This document outlines the complete document submission workflow that gets triggered after a lawyer accepts a case request from a client. The system ensures clients provide all necessary legal documents for case processing.

## Workflow Flow

### 1. **Lawyer Accepts Case Request**
- Location: `lawyers/views.py` → `case_request_accept_view()`
- When a lawyer accepts a case request:
  - Case status changes to `DOCUMENTS_PENDING`
  - Workflow stage changes to `DOCUMENT_VERIFICATION`
  - Notification is sent to the client with upload link

### 2. **Client Receives Notification**
- Client receives notification with link to upload documents: `/cases/{case_request_id}/upload-documents/`
- The client can navigate from their "My Cases" page by clicking "Upload Documents" button

### 3. **Document Upload Page**
- Location: `clients/templates/case_document_upload.html`
- Displays:
  - **Client Information Panel**
    - Full name
    - Email
    - Mobile number
    - Gender
    - Date of birth
    - Marital status
  - **Case Details Panel**
    - Assigned lawyer name and specialization
    - Case creation date
    - Current case status
  - **Document Upload Form**
    - 7 document types with drag-and-drop interface
    - Visual file upload indicators
    - Form validation
  - **Information Panels**
    - Important guidelines
    - Document requirements
    - Assigned lawyer contact info

### 4. **Document Types Supported**
1. **Aadhaar Card** - ID proof (both sides required)
2. **PAN Card** - Tax ID
3. **Marriage Certificate** - Proof of marriage
4. **Address Proof** - Utility bill or postal address proof
5. **Income Proof** - ITR, salary slip, or bank statement
6. **Passport** - Travel ID
7. **Affidavits** - Legal declarations

### 5. **Document Upload Processing**
- Location: `lawyers/views.py` → `case_document_upload_view()`
- Accepts file types: PDF, JPG, PNG, DOCX
- Process:
  1. Client uploads one or more documents
  2. Form validates at least one document is uploaded
  3. For each document:
     - Checks if document type already exists for the case
     - If exists: updates the file
     - If new: creates CaseDocument record
     - Creates CaseDocumentVerification record with status "PENDING"
  4. Case status changes to `DOCUMENTS_SUBMITTED`
  5. Lawyer and admin receive notifications

### 6. **Document Verification**
- Location: `adminpanel/templates/case_details_for_admin.html`
- Admin verifies documents:
  - Status options: PENDING, VERIFIED, REJECTED
  - Can provide rejection reason if needed
  - Once all documents verified, case proceeds to next workflow stage

## Database Models

### CaseRequest Model
```python
- client: ForeignKey to ClientProfile
- lawyer: ForeignKey to LawyerProfile
- status: ['PENDING', 'DOCUMENTS_PENDING', 'DOCUMENTS_SUBMITTED', 'DOCUMENTS_VERIFIED', ...]
- workflow_stage: Tracks case progress through workflow stages
- response_message: Optional lawyer response message
```

### CaseDocument Model
```python
- case_request: ForeignKey to CaseRequest
- document_type: Choice field from DOCUMENT_TYPES
- document_file: FileField (uploaded to case_documents/%Y/%m/%d/)
- uploaded_at: Timestamp when document was uploaded
```

### CaseDocumentVerification Model
```python
- document: ForeignKey to CaseDocument
- status: ['PENDING', 'VERIFIED', 'REJECTED']
- rejection_reason: Optional reason if rejected
```

## Forms

### CaseDocumentBulkUploadForm
- Bulk upload form for all 7 document types
- Fields are optional individually but requires at least one
- All fields accept: PDF, JPG, PNG, DOCX
- Form includes validation in `clean()` method

## Templates

### case_document_upload.html (NEW)
Professional document submission form with:
- Client information display
- Case details display
- 7 document upload sections with drag-and-drop UI
- Important guidelines and requirements
- Assigned lawyer information card
- File validation with visual feedback

### client_cases.html (UPDATED)
Added "Upload Documents" button that appears when:
- Case status is `DOCUMENTS_PENDING`
- Links to: `/cases/{case_request.id}/upload-documents/`

## URLs

All URLs are already configured in `clients/urls.py`:
```
/cases/<int:case_request_id>/upload-documents/  → case_document_upload_view
/cases/<int:case_request_id>/documents-status/  → case_documents_status_view
```

## Views

### case_document_upload_view
- **Location**: `lawyers/views.py`
- **Access**: Requires client profile (login required)
- **Method**: GET (display form) / POST (process upload)
- **Validation**: Case must be in PENDING or DOCUMENTS_PENDING status
- **Returns**: Renders case_document_upload.html with context:
  - `form`: CaseDocumentBulkUploadForm instance
  - `case_request`: Current case request object
  - `client_profile`: Client's profile object
  - `user`: Authenticated user object
  - `uploaded_documents`: Already uploaded documents

## Notification System

### When Lawyer Accepts Request
```
Notification sent to CLIENT:
- Title: "Lawyer accepted request - Documents needed"
- Message: "{Lawyer name} has accepted your request. Please upload required documents to proceed."
- URL: /cases/{case_request_id}/upload-documents/
```

### When Client Submits Documents
```
Notification sent to LAWYER:
- Title: "Documents uploaded for case"
- Message: "{Client name} has submitted documents for the case."
- URL: /lawyers/case/{case_request_id}/view-documents/

Notification sent to ADMIN:
- For verification and approval
```

## Status Flow

```
Initial State: PENDING
    ↓
Lawyer accepts → DOCUMENTS_PENDING
    ↓
Client uploads → DOCUMENTS_SUBMITTED
    ↓
Admin verifies → DOCUMENTS_VERIFIED
    ↓
Continue with case → Workflow stages proceed
```

## Key Features

1. **User-Friendly Interface**
   - Clear, modern design with Tailwind CSS
   - Drag-and-drop file upload zones
   - Visual file selection feedback
   - File size display

2. **Comprehensive Information Display**
   - Client details are pre-populated
   - Lawyer information with rating
   - Case tracking progress
   - Important guidelines and document requirements

3. **Validation**
   - Client-side: At least one document required
   - Server-side: File type validation, document uniqueness
   - User feedback: Clear error messages

4. **Notifications**
   - Real-time updates for all parties
   - Direct links to take action
   - Status tracking throughout workflow

5. **Document Organization**
   - Organized by document type
   - Timestamped uploads
   - Verification tracking
   - Rejection reasons logged

## How to Use

### For Clients:
1. Receive notification when lawyer accepts request
2. Click "Upload Documents" in My Cases page or notification link
3. Review personal and case details on the form
4. Upload required documents by dragging/clicking
5. Review upload status and click "Submit Documents"
6. Receive confirmation and wait for admin verification

### For Lawyers:
1. Receive notification when accepting case (current flow)
2. Can view submitted documents in admin panel
3. Monitor document verification status

### For Admin:
1. Review uploaded documents in admin panel
2. Verify or reject each document
3. Provide feedback if needed
4. Once verified, case proceeds to next stage

## File Structure

```
clients/
├── templates/
│   ├── client_cases.html (UPDATED - added upload button)
│   └── case_document_upload.html (NEW)
└── urls.py (already configured)

lawyers/
├── views.py (case_document_upload_view)
├── forms.py (CaseDocumentBulkUploadForm)
└── models.py (CaseRequest, CaseDocument, CaseDocumentVerification)

adminpanel/
└── templates/
    └── case_details_for_admin.html (displays documents)
```

## Testing the Feature

1. **Setup**:
   - Create a lawyer profile and get verified
   - Create a client profile
   - Client sends case request to lawyer

2. **Flow**:
   - Lawyer login → Accept case request
   - Client login → Navigate to My Cases
   - Click "Upload Documents" button
   - Upload at least one document and submit
   - Verify case status changes to DOCUMENTS_SUBMITTED

3. **Admin**:
   - Login to admin panel
   - View case documents
   - Verify or reject documents
   - Observe status updates

## Security Considerations

1. **Access Control**
   - Only clients can upload documents
   - Only for their own cases
   - Case must be in correct status

2. **File Upload**
   - Restricted file types (PDF, JPG, PNG, DOCX)
   - Files stored in organized directory structure
   - Timestamped for audit trail

3. **Data Privacy**
   - Client information only shown to authenticated users
   - Documents stored securely
   - Notification links are case-specific

## Future Enhancements

1. **Document Re-upload**
   - Allow clients to re-upload rejected documents
   - Automatic notification and link to update

2. **Document Preview**
   - In-browser preview for uploaded documents
   - Before final submission

3. **Progress Tracking**
   - Timeline view of document verification
   - Status updates in client dashboard

4. **Email Notifications**
   - Send email alerts when documents uploaded
   - Email confirmation of verification status

5. **Document Templates**
   - Provide downloadable document templates
   - Guide clients on proper document format
