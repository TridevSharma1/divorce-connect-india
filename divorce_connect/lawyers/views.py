from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from lawyers.forms import LawyerProfileEditForm, CaseDocumentBulkUploadForm, DocumentVerificationForm
from lawyers.models import LawyerProfile, LawyerProfileUpdateRequest, CaseRequest, CaseDocument, CaseDocumentVerification
from clients.models import ClientProfile
from adminpanel.models import TrustReport
from accounts.models import Notification
from core_decorators import require_verified_profile

def lawyer_section_view(request):
    """Public marketplace page where clients search for lawyers."""
    verified_lawyers = LawyerProfile.objects.filter(
        verified=True,
        is_profile_complete=True
    ).select_related('user').order_by('-rating')
    return render(request, 'lawyers_section.html', {'verified_lawyers': verified_lawyers})

def lawyer_detail_view(request, lawyer_id):
    """Show single lawyer's profile with all details."""
    try:
        lawyer = LawyerProfile.objects.get(id=lawyer_id, verified=True, is_profile_complete=True)
    except LawyerProfile.DoesNotExist:
        return redirect('/lawyers/')

    client_request = None
    is_client = request.user.is_authenticated and hasattr(request.user, 'client_profile')
    if is_client:
        client_request = CaseRequest.objects.filter(
            client=request.user.client_profile,
            lawyer=lawyer,
            status__in=['PENDING', 'ACCEPTED']
        ).order_by('-created_at').first()

    if request.method == 'POST':
        if not is_client:
            return redirect('/api/auth/login/')

        if client_request:
            messages.warning(request, "You already have an active request with this lawyer.")
            return redirect('lawyer_detail', lawyer_id=lawyer.id)

        message = request.POST.get('message', '').strip()
        case_request = CaseRequest.objects.create(
            client=request.user.client_profile,
            lawyer=lawyer,
            message=message
        )

        Notification.objects.create(
            user=lawyer.user,
            title='New lawyer hire request',
            message=f'{request.user.client_profile.get_full_name()} has requested to hire you.',
            url='/lawyers/orders/'
        )

        messages.success(request, "Your request has been sent. The lawyer will review it soon.")
        return redirect('lawyer_detail', lawyer_id=lawyer.id)

    return render(request, 'lawyer_detail.html', {
        'lawyer': lawyer,
        'client_request': client_request,
    })


@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def case_request_accept_view(request, request_id):
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest,
        id=request_id,
        lawyer=request.user.lawyer_profile,
        status='PENDING'
    )

    if request.method == 'POST':
        # Change status to waiting for documents
        case_request.status = 'DOCUMENTS_PENDING'
        case_request.workflow_stage = 'DOCUMENT_VERIFICATION'
        case_request.workflow_stage_updated_at = timezone.now()
        case_request.response_message = request.POST.get('response_message', '').strip()
        case_request.save()

        Notification.objects.create(
            user=case_request.client.user,
            title='Lawyer accepted request - Documents needed',
            message=f'{request.user.lawyer_profile.full_name} has accepted your request. Please upload required documents to proceed.',
            url=f'/cases/{case_request.id}/upload-documents/'
        )

        messages.success(request, "Request accepted! Client will now upload documents.")
    return redirect('lawyer_case_orders')


@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def case_request_reject_view(request, request_id):
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest,
        id=request_id,
        lawyer=request.user.lawyer_profile,
        status='PENDING'
    )

    if request.method == 'POST':
        case_request.status = 'REJECTED'
        case_request.response_message = request.POST.get('response_message', '').strip()
        case_request.save()

        Notification.objects.create(
            user=case_request.client.user,
            title='Hire request rejected',
            message=f'{request.user.lawyer_profile.full_name} rejected your hire request.',
            url='/cases/'
        )

        messages.warning(request, "The request has been rejected and the client has been notified.")
    return redirect('lawyer_case_orders')


@login_required(login_url='/api/auth/login/')
def lawyer_profile_edit_view(request):
    """Handles both Initial Onboarding AND Future Profile Updates."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    profile = request.user.lawyer_profile

    # ==========================================
    # PATH A: INITIAL SETUP (Not Verified Yet)
    # Uses your existing Django Form setup
    # ==========================================
    if not profile.verified:
        if request.method == 'POST':
            form = LawyerProfileEditForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save(commit=False)
                profile.is_profile_complete = True
                profile.save()

                # Create or update initial verification request
                from adminpanel.models import LawyerVerificationRequest
                verification_request, created = LawyerVerificationRequest.objects.get_or_create(
                    lawyer=profile
                )
                if created:
                    messages.success(request, 'Profile submitted successfully! Admin will review your request soon.')
                else:
                    messages.info(request, 'Profile updated! Admin will review the changes.')

                return redirect('/lawyers/dashboard/')
        else:
            form = LawyerProfileEditForm(instance=profile)

        return render(request, 'lawyer_profile_edit.html', {'form': form})

    # ==========================================
    # PATH B: FUTURE EDITS (Already Verified)
    # Uses the Shadow Model (LawyerProfileUpdateRequest)
    # ==========================================
    else:
        pending_update = LawyerProfileUpdateRequest.objects.filter(lawyer=profile, status='PENDING').first()

        if request.method == 'POST':
            if pending_update:
                messages.warning(request, "You already have a profile update pending approval.")
                return redirect('/lawyers/profile/edit/')

            update_request = LawyerProfileUpdateRequest(
                lawyer=profile,
                full_name=request.POST.get('full_name'),
                gender=request.POST.get('gender'),
                years_of_experience=request.POST.get('years_of_experience') or profile.years_of_experience,
                specialization=request.POST.get('specialization'),
                consultation_fee=request.POST.get('consultation_fee') or profile.consultation_fee,
                office_city=request.POST.get('office_city'),
                bio=request.POST.get('bio'),
                mobile_number=request.POST.get('mobile_number'),
                alternate_mobile_number=request.POST.get('alternate_mobile_number'),
            )
            
            dob = request.POST.get('date_of_birth')
            if dob:
                update_request.date_of_birth = dob
                
            if 'profile_picture' in request.FILES:
                update_request.profile_picture = request.FILES['profile_picture']
                
            update_request.save()
            messages.success(request, "Your profile updates have been submitted and are pending admin approval.")
            return redirect('/lawyers/profile/edit/')

        context = {
            'profile': profile,
            'has_pending_update': pending_update is not None,
        }
        return render(request, 'edit_profile_lawyer.html', context)


@login_required(login_url='/api/auth/login/')
def lawyer_delete_account_view(request):
    """The 'Delete' part of RUD operations."""
    if request.method == 'POST':
        user = request.user
        if hasattr(user, 'lawyer_profile'):
            user.lawyer_profile.soft_delete()
            logout(request)
            messages.success(request, "Your practice account has been deleted. Contact support to reactivate it.")
            return redirect('/')
    return redirect('/lawyers/profile/edit/')


@login_required(login_url='/api/auth/login/')
def lawyer_profile_view(request):
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    profile = request.user.lawyer_profile
    return render(request, 'profile_lawyer.html', {'profile': profile})

@login_required(login_url='/api/auth/login/')
def lawyer_dashboard_view(request):
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    profile = request.user.lawyer_profile
    has_pending_update = LawyerProfileUpdateRequest.objects.filter(lawyer=profile, status='PENDING').exists()
    
    # Fetch accepted cases for recent clients display
    recent_clients = CaseRequest.objects.filter(
        lawyer=profile,
        status='ACCEPTED'
    ).select_related('client', 'client__user').order_by('-updated_at')[:4]
    
    context = {
        'profile': profile,
        'is_verified': profile.verified,
        'is_complete': profile.is_profile_complete,
        'has_pending_update': has_pending_update,
        'recent_clients': recent_clients,
    }
    return render(request, 'lawyer_dashboard.html', context)

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def earning_dashboard_view(request):
    """Secure financial dashboard for lawyers."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'earning_dashboard.html')

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def case_order_view(request):
    """Inbox for lawyers to view incoming consultation requests."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    pending_requests = CaseRequest.objects.filter(
        lawyer=request.user.lawyer_profile,
        status='PENDING'
    ).select_related('client', 'client__user').order_by('-created_at')

    return render(request, 'case_order.html', {
        'pending_requests': pending_requests,
    })


@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def case_status_view(request):
    """Operational CRM view for lawyers to manage active clients."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    # Cases ready to be accepted (all documents verified)
    ready_cases = CaseRequest.objects.filter(
        lawyer=request.user.lawyer_profile,
        status='DOCUMENTS_VERIFIED'
    ).select_related('client', 'client__user').prefetch_related('case_documents').order_by('-updated_at')
    
    # Active cases already accepted
    active_cases = CaseRequest.objects.filter(
        lawyer=request.user.lawyer_profile,
        status='ACCEPTED'
    ).select_related('client', 'client__user').order_by('-updated_at')
    
    # Cases pending document verification
    pending_verification_cases = CaseRequest.objects.filter(
        lawyer=request.user.lawyer_profile,
        status__in=['PENDING', 'DOCUMENTS_PENDING', 'DOCUMENTS_SUBMITTED']
    ).select_related('client', 'client__user').prefetch_related('case_documents', 'case_documents__casedocumentverification').order_by('-updated_at')
    
    # Rejected cases
    rejected_cases = CaseRequest.objects.filter(
        lawyer=request.user.lawyer_profile,
        status='REJECTED'
    ).select_related('client', 'client__user').order_by('-updated_at')

    return render(request, 'case_status.html', {
        'ready_cases': ready_cases,
        'active_cases': active_cases,
        'pending_verification_cases': pending_verification_cases,
        'rejected_cases': rejected_cases,
    })

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def account_settings_view(request):
    """Backend settings for lawyer availability, security, and notifications."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'account_settings.html')

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def billing_payment_view(request):
    """Secure page for lawyer payouts, taxes, and invoices."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'billing_payment.html')

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def support_lawyer_view(request):
    """Priority help center and ticketing for lawyers."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'support_lawyer.html')

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def report_client_view(request):
    """Trust and safety page for lawyers to report abusive clients."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    current_lawyer = request.user.lawyer_profile
    available_clients = current_lawyer.case_requests.filter(
        status__in=['PENDING', 'DOCUMENTS_PENDING', 'DOCUMENTS_SUBMITTED', 'DOCUMENTS_VERIFIED', 'ACCEPTED']
    ).select_related('client', 'client__user').order_by('-created_at')

    if request.method == 'POST':
        client_id = request.POST.get('client')
        reason = request.POST.get('reason', '').strip()
        description = request.POST.get('description', '').strip()
        evidence = request.FILES.get('evidence')

        if not client_id or not reason or not description:
            messages.error(request, 'Please select a client and provide a reason and incident description.')
            return render(request, 'report_client.html', {
                'clients': [cr.client for cr in available_clients],
            })

        reported_client = get_object_or_404(
            ClientProfile,
            id=client_id
        )
        TrustReport.objects.create(
            reporter=request.user,
            reported_client=reported_client,
            reason=reason,
            description=description,
            evidence=evidence
        )

        Notification.objects.create(
            user=request.user,
            title='Report Submitted',
            message=f'Your report against {reported_client.get_full_name()} has been received and is under review.',
            url='/lawyers/dashboard/'
        )
        Notification.objects.create(
            user=reported_client.user,
            title='A report has been filed against you',
            message=f'{current_lawyer.full_name} has submitted a report. Admin will review and take action.',
            url='/dashboard/'
        )

        if reported_client.report_count >= 3:
            messages.warning(request, 'This client now has 3 or more reports and is eligible for ban review by the admin.')

        messages.success(request, 'Your report has been submitted successfully. Thank you for keeping the community safe.')
        return redirect('lawyer_dashboard')

    return render(request, 'report_client.html', {
        'clients': [cr.client for cr in available_clients],
    })


@login_required(login_url='/api/auth/login/')
def case_document_upload_view(request, case_request_id):
    """Allow clients to upload documents for a case request."""
    if not hasattr(request.user, 'client_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest,
        id=case_request_id,
        client=request.user.client_profile
    )

    # Check if case request is still in pending or waiting for documents state
    if case_request.status not in ['PENDING', 'DOCUMENTS_PENDING']:
        messages.warning(request, "Documents cannot be uploaded for this case.")
        return redirect('client_cases')

    if request.method == 'POST':
        form = CaseDocumentBulkUploadForm(request.POST, request.FILES, case_request=case_request)
        if form.is_valid():
            # Process each uploaded document
            document_types = ['aadhaar', 'pan', 'marriage_cert', 'address_proof', 'income_proof', 'passport', 'affidavit']
            documents_created = 0

            for doc_type in document_types:
                if doc_type in request.FILES:
                    file = request.FILES[doc_type]
                    # Check if document already exists
                    existing = CaseDocument.objects.filter(
                        case_request=case_request,
                        document_type=doc_type
                    ).first()

                    if existing:
                        existing.document_file = file
                        existing.save()
                    else:
                        CaseDocument.objects.create(
                            case_request=case_request,
                            document_type=doc_type,
                            document_file=file
                        )
                        # Create verification record
                        doc = CaseDocument.objects.get(
                            case_request=case_request,
                            document_type=doc_type
                        )
                        CaseDocumentVerification.objects.get_or_create(document=doc)
                    documents_created += 1

            if documents_created > 0:
                case_request.status = 'DOCUMENTS_SUBMITTED'
                case_request.workflow_stage = 'DOCUMENT_VERIFICATION'
                case_request.workflow_stage_updated_at = timezone.now()
                case_request.documents_submitted_at = timezone.now()
                case_request.save()

                # Notify lawyer and admin
                Notification.objects.create(
                    user=case_request.lawyer.user,
                    title='Documents uploaded for case',
                    message=f'{request.user.client_profile.get_full_name()} has submitted documents for the case.',
                    url=f'/lawyers/case/{case_request.id}/view-documents/'
                )

                messages.success(request, f"Successfully uploaded {documents_created} document(s). Waiting for admin verification.")
                return redirect('client_cases')
            else:
                messages.error(request, "No documents were uploaded. Please try again.")
        else:
            messages.error(request, str(form.errors))
    else:
        form = CaseDocumentBulkUploadForm(case_request=case_request)

    # Get already uploaded documents
    uploaded_documents = CaseDocument.objects.filter(case_request=case_request)

    return render(request, 'case_document_upload.html', {
        'form': form,
        'case_request': case_request,
        'uploaded_documents': uploaded_documents,
        'client_profile': request.user.client_profile,
        'user': request.user,
    })


@login_required(login_url='/api/auth/login/')
def case_documents_status_view(request, case_request_id):
    """View document submission status for clients."""
    if not hasattr(request.user, 'client_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest,
        id=case_request_id,
        client=request.user.client_profile
    )

    documents = CaseDocument.objects.filter(case_request=case_request).prefetch_related('casedocumentverification')

    return render(request, 'case_documents_status.html', {
        'case_request': case_request,
        'documents': documents,
    })


@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def lawyer_view_case_documents(request, case_request_id):
    """Allow lawyers to view documents only after verification."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest,
        id=case_request_id,
        lawyer=request.user.lawyer_profile
    )

    # Show pending message if documents not verified
    documents = CaseDocument.objects.filter(case_request=case_request).prefetch_related('casedocumentverification')

    return render(request, 'lawyer_view_case_documents.html', {
        'case_request': case_request,
        'documents': documents,
    })


@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def lawyer_accept_case_view(request, case_request_id):
    """Lawyer accepts the case after documents are verified."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest,
        id=case_request_id,
        lawyer=request.user.lawyer_profile,
        status='DOCUMENTS_VERIFIED'
    )

    if request.method == 'POST':
        case_request.status = 'ACCEPTED'
        case_request.workflow_stage = 'LAWYER_ASSIGNED'
        case_request.workflow_stage_updated_at = timezone.now()
        case_request.response_message = request.POST.get('response_message', '').strip()
        case_request.save()

        Notification.objects.create(
            user=case_request.client.user,
            title='Case accepted by lawyer',
            message=f'{request.user.lawyer_profile.full_name} has accepted your case and verified your documents.',
            url='/cases/'
        )

        messages.success(request, "Case accepted! You can now access all client documents.")
        return redirect('lawyer_case_status')

    return render(request, 'lawyer_accept_case.html', {'case_request': case_request})


@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def lawyer_advance_case_stage_view(request, case_request_id):
    """Advance the case to the next workflow milestone."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest,
        id=case_request_id,
        lawyer=request.user.lawyer_profile,
        status__in=['ACCEPTED', 'COMPLETED']
    )

    if request.method == 'POST':
        if case_request.workflow_stage == 'COMPLETED':
            messages.info(request, 'This case is already completed.')
            return redirect('lawyer_view_case_documents', case_request_id=case_request.id)

        next_stage = case_request.next_workflow_stage
        if not next_stage:
            messages.warning(request, 'No further workflow stage is available.')
            return redirect('lawyer_view_case_documents', case_request_id=case_request.id)

        case_request.workflow_stage = next_stage
        case_request.workflow_stage_updated_at = timezone.now()

        if next_stage == 'COMPLETED':
            case_request.status = 'COMPLETED'

        case_request.save()

        Notification.objects.create(
            user=case_request.client.user,
            title='Case progressed',
            message=f'Your case has moved to "{dict(case_request.WORKFLOW_STAGES).get(next_stage)}".',
            url='/cases/'
        )

        messages.success(request, f'Case progressed to {dict(case_request.WORKFLOW_STAGES).get(next_stage)}.')

    return redirect('lawyer_view_case_documents', case_request_id=case_request.id)
