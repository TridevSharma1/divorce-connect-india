from decimal import Decimal
import calendar

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from lawyers.forms import LawyerProfileEditForm, CaseDocumentBulkUploadForm, DocumentVerificationForm
from lawyers.models import LawyerProfile, LawyerProfileUpdateRequest, CaseRequest, CaseDocument, CaseDocumentVerification, CaseMessage, LawyerRating
from clients.models import ClientProfile
from adminpanel.models import TrustReport
from accounts.models import Notification
from core_decorators import require_verified_profile
from utils.email_utils import send_case_accepted_email, send_report_submitted_email

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
        has_rated = LawyerRating.objects.filter(
            client=request.user.client_profile,
            lawyer=lawyer
        ).exists()
    else:
        has_rated = False

    if request.method == 'POST':
        if not is_client:
            return redirect('/api/auth/login/')

        if request.POST.get('form_type') == 'rating':
            rating_value = int(request.POST.get('rating', '0') or 0)
            if rating_value < 1 or rating_value > 5:
                messages.error(request, 'Please select a valid star rating before submitting.')
                return redirect('lawyer_detail', lawyer_id=lawyer.id)

            if has_rated:
                messages.warning(request, 'You have already rated this lawyer.')
                return redirect('lawyer_detail', lawyer_id=lawyer.id)

            review_text = request.POST.get('review_text', '').strip()
            LawyerRating.objects.create(
                lawyer=lawyer,
                client=request.user.client_profile,
                score=rating_value,
                review_text=review_text
            )

            lawyer.add_rating(rating_value)
            messages.success(request, 'Thanks for rating this lawyer! Your star rating has been recorded.')
            return redirect('lawyer_detail', lawyer_id=lawyer.id)

        if client_request:
            messages.warning(request, "You already have an active request with this lawyer.")
            return redirect('lawyer_detail', lawyer_id=lawyer.id)

        # Check if client profile is complete
        client_profile = request.user.client_profile
        if not client_profile.first_name or not client_profile.mobile_number or not client_profile.address or not client_profile.pincode:
            messages.warning(request, 'Profile Incomplete: Please provide your full name, mobile number, and address in your profile before submitting a hire request to a lawyer.')
            return redirect('client_profile')

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
        'has_rated': has_rated,
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
                
                # Auto-send notification on profile update
                from accounts.models import Notification
                Notification.objects.create(
                    user=request.user,
                    title="Profile Saved",
                    message="Your profile has been saved successfully and is pending admin verification.",
                    url="/lawyers/profile/"
                )

                # Notify all admin users
                from accounts.models import BaseUser
                for admin in BaseUser.objects.filter(is_staff=True, is_active=True):
                    Notification.objects.create(
                        user=admin,
                        title="New Lawyer Verification Request",
                        message=f"Lawyer {profile.full_name} has submitted a verification request.",
                        url=f"/adminpanel/lawyer/{profile.id}/verify/"
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

            consultation_fee_value = request.POST.get('consultation_fee')
            if not consultation_fee_value:
                messages.error(request, "Consultation fee is required.")
                return redirect('/lawyers/profile/edit/')

            update_request = LawyerProfileUpdateRequest(
                lawyer=profile,
                full_name=request.POST.get('full_name'),
                gender=request.POST.get('gender'),
                years_of_experience=request.POST.get('years_of_experience') or profile.years_of_experience,
                specialization=request.POST.get('specialization'),
                consultation_fee=consultation_fee_value,
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
            
            # Auto-send notification on profile update request submission
            from accounts.models import Notification
            Notification.objects.create(
                user=request.user,
                title="Profile Update Submitted",
                message="Your profile updates have been submitted and are pending admin approval.",
                url="/lawyers/profile/"
            )

            # Notify all admin users
            from accounts.models import BaseUser
            for admin in BaseUser.objects.filter(is_staff=True, is_active=True):
                Notification.objects.create(
                    user=admin,
                    title="Lawyer Profile Update Request",
                    message=f"Lawyer {profile.full_name} has requested a profile update.",
                    url=f"/adminpanel/lawyer/update-request/{update_request.id}/"
                )
            
            messages.success(request, "Your profile updates have been submitted and are pending admin approval.")
            return redirect('/lawyers/profile/edit/')

        context = {
            'profile': profile,
            'has_pending_update': pending_update is not None,
        }
        return render(request, 'edit_profile_lawyer.html', context)


@login_required(login_url='/api/auth/login/')
def lawyer_delete_account_view(request):
    """Redirect to the unified email-confirmed account deletion flow."""
    return redirect('/api/auth/delete-account/')


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

    base_queryset = CaseRequest.objects.filter(lawyer=profile)
    pending_requests_qs = base_queryset.filter(status='PENDING')
    ready_cases_qs = base_queryset.filter(status='DOCUMENTS_VERIFIED')
    accepted_cases_qs = base_queryset.filter(status='ACCEPTED')

    pending_requests = pending_requests_qs.select_related('client', 'client__user').order_by('-created_at')[:5]
    ready_cases = ready_cases_qs.select_related('client', 'client__user').order_by('-updated_at')[:5]
    recent_clients = accepted_cases_qs.select_related('client', 'client__user').order_by('-updated_at')[:4]

    total_cases = base_queryset.count()
    pending_count = pending_requests_qs.count()
    active_cases_count = accepted_cases_qs.count()
    completed_cases_count = base_queryset.filter(status='COMPLETED').count()
    verified_documents = CaseDocumentVerification.objects.filter(
        document__case_request__lawyer=profile,
        status='VERIFIED'
    ).count()
    pending_document_reviews = CaseDocumentVerification.objects.filter(
        document__case_request__lawyer=profile,
        status='PENDING'
    ).count()
    active_clients_count = accepted_cases_qs.values('client').distinct().count()

    now = timezone.now()
    consultation_fee = profile.consultation_fee or 0
    monthly_accepted_count = accepted_cases_qs.filter(updated_at__year=now.year, updated_at__month=now.month).count()
    yearly_accepted_count = accepted_cases_qs.filter(updated_at__year=now.year).count()

    context = {
        'profile': profile,
        'is_verified': profile.verified,
        'is_complete': profile.is_profile_complete,
        'has_pending_update': has_pending_update,
        'pending_requests': pending_requests,
        'ready_cases': ready_cases,
        'recent_clients': recent_clients,
        'stats': {
            'total_cases': total_cases,
            'pending_requests': pending_count,
            'active_cases': active_cases_count,
            'completed_cases': completed_cases_count,
            'verified_documents': verified_documents,
            'pending_document_reviews': pending_document_reviews,
            'active_clients': active_clients_count,
            'monthly_revenue': consultation_fee * monthly_accepted_count,
            'yearly_revenue': consultation_fee * yearly_accepted_count,
        },
    }
    return render(request, 'lawyer_dashboard.html', context)

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def earning_dashboard_view(request):
    """Secure financial dashboard for lawyers."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    profile = request.user.lawyer_profile
    base_queryset = CaseRequest.objects.filter(lawyer=profile)
    completed_qs = base_queryset.filter(status='COMPLETED')
    accepted_qs = base_queryset.filter(status='ACCEPTED')
    active_qs = base_queryset.filter(status__in=['ACCEPTED', 'COMPLETED'])
    consultation_fee = profile.consultation_fee or Decimal('0.00')

    total_generated_amount = consultation_fee * active_qs.count()
    available_balance = consultation_fee * completed_qs.count()
    escrow_balance = consultation_fee * accepted_qs.count()

    now = timezone.now()
    revenue_by_month = []
    max_monthly_amount = Decimal('0.00')
    for offset in range(5, -1, -1):
        total_months = now.year * 12 + now.month - 1 - offset
        year, month_index = divmod(total_months, 12)
        month = month_index + 1
        month_label = calendar.month_abbr[month]
        month_cases = active_qs.filter(updated_at__year=year, updated_at__month=month).count()
        month_amount = consultation_fee * month_cases
        if month_amount > max_monthly_amount:
            max_monthly_amount = month_amount
        revenue_by_month.append({
            'label': month_label,
            'amount': month_amount,
        })

    chart_bars = []
    for item in revenue_by_month:
        if max_monthly_amount > 0:
            height_pct = int((item['amount'] / max_monthly_amount) * 100)
        else:
            height_pct = 0
        if item['amount'] > 0 and height_pct < 10:
            height_pct = 10
        chart_bars.append({
            'label': item['label'],
            'amount': item['amount'],
            'height_pct': height_pct,
            'is_current': item['label'] == calendar.month_abbr[now.month],
        })

    recent_transactions = base_queryset.filter(
        status__in=['COMPLETED', 'ACCEPTED', 'PENDING', 'DOCUMENTS_VERIFIED']
    ).select_related('client').order_by('-updated_at')[:10]

    status_map = {
        'COMPLETED': {'label': 'Completed', 'dot_class': 'bg-black'},
        'ACCEPTED': {'label': 'Accepted', 'dot_class': 'bg-blue-500'},
        'PENDING': {'label': 'Pending', 'dot_class': 'bg-gray-400'},
        'DOCUMENTS_VERIFIED': {'label': 'Verified', 'dot_class': 'bg-green-500'},
        'DOCUMENTS_PENDING': {'label': 'Documents Pending', 'dot_class': 'bg-yellow-400'},
        'DOCUMENTS_SUBMITTED': {'label': 'Submitted', 'dot_class': 'bg-yellow-600'},
        'REJECTED': {'label': 'Rejected', 'dot_class': 'bg-red-500'},
    }

    transactions = []
    for case in recent_transactions:
        status_info = status_map.get(case.status, {
            'label': case.get_status_display(),
            'dot_class': 'bg-gray-400'
        })
        transactions.append({
            'date': case.updated_at.strftime('%b %d, %Y'),
            'client_name': case.client.get_full_name(),
            'consultation_type': 'Lawyer Consultation',
            'amount': consultation_fee,
            'status_label': status_info['label'],
            'status_dot_class': status_info['dot_class'],
        })

    context = {
        'profile': profile,
        'totals': {
            'total_earnings': total_generated_amount,
            'escrow_balance': escrow_balance,
            'available_balance': available_balance,
            'monthly_generated': chart_bars[-1]['amount'] if chart_bars else Decimal('0.00'),
        },
        'chart_bars': chart_bars,
        'transactions': transactions,
        'transactions_total': base_queryset.count(),
    }

    return render(request, 'earning_dashboard.html', context)

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
        report = TrustReport.objects.create(
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

        # Notify all admin users
        from accounts.models import BaseUser
        for admin in BaseUser.objects.filter(is_staff=True, is_active=True):
            Notification.objects.create(
                user=admin,
                title="New Trust Report Filed",
                message=f"Lawyer {current_lawyer.full_name} reported Client {reported_client.get_full_name()}.",
                url=f"/adminpanel/reports/{report.id}/"
            )

        # Send confirmation email to the reporting lawyer
        try:
            send_report_submitted_email(
                reporter_name=current_lawyer.full_name,
                reporter_email=request.user.email,
                reported_name=reported_client.get_full_name(),
                report_reason=reason,
            )
        except Exception:
            pass

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

                # Notify all admin users
                from accounts.models import BaseUser
                for admin in BaseUser.objects.filter(is_staff=True, is_active=True):
                    Notification.objects.create(
                        user=admin,
                        title='New Case Documents Submitted',
                        message=f'Client {request.user.client_profile.get_full_name()} submitted documents for case #{case_request.id}.',
                        url='/adminpanel/documents/verify/'
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

        # Send operational email to client with lawyer details
        try:
            send_case_accepted_email(case_request)
        except Exception:
            pass

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


@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def lawyer_case_detail_view(request, case_id):
    """Detailed view for an active case, showing verified documents and a chat interface."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    case_request = get_object_or_404(
        CaseRequest, 
        id=case_id, 
        lawyer=request.user.lawyer_profile, 
        status__in=['ACCEPTED', 'COMPLETED']
    )

    # Handle sending a new message
    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        
        if message_text or attachment:
            CaseMessage.objects.create(
                case=case_request,
                sender_type='LAWYER',
                sender_user=request.user,
                text=message_text,
                attachment=attachment
            )
            # Create a notification for the client
            Notification.objects.create(
                user=case_request.client.user,
                title='New message from your lawyer',
                message=f'You have a new message regarding your case: {case_request.id}',
                url=f'/cases/?active_case={case_request.id}' # Update URL to the new split-view
            )
        return redirect('lawyer_case_detail', case_id=case_id)

    # Fetch ONLY verified documents
    verified_documents = CaseDocument.objects.filter(
        case_request=case_request,
        casedocumentverification__status='VERIFIED'
    )

    # Fetch all messages for this case
    messages_list = case_request.messages.all().select_related('sender_user')

    context = {
        'case_request': case_request,
        'verified_documents': verified_documents,
        'messages': messages_list,
    }
    return render(request, 'lawyer_case_detail.html', context)
