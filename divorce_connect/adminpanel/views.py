from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from adminpanel.forms import AdminProfileEditForm
from adminpanel.models import LawyerVerificationRequest, AdminPanelProfileUpdateRequest, TrustReport
from lawyers.models import LawyerProfile, LawyerProfileUpdateRequest, CaseRequest, CaseDocument, CaseDocumentVerification
from lawyers.forms import DocumentVerificationForm
from accounts.models import Notification
from utils.email_utils import send_report_action_to_reporter, send_report_action_to_reported


def is_admin_staff(user):
    """Check if user is an admin staff member."""
    return hasattr(user, 'admin_profile') and user.is_staff


@login_required(login_url='/api/auth/login/')
def admin_profile_edit_view(request):
    """Profile edit view - for completing profile after registration."""
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')

    profile = request.user.admin_profile

    if request.method == 'POST':
        form = AdminProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            if profile.is_verified_by_superuser:
                pending_request = AdminPanelProfileUpdateRequest.objects.filter(
                    admin_profile=profile,
                    status='PENDING'
                ).first()
                if pending_request:
                    messages.warning(request, 'You already have a pending profile update request. Please wait for approval.')
                    return redirect('admin_profile_edit')

                update_request = AdminPanelProfileUpdateRequest(
                    admin_profile=profile,
                    full_name=form.cleaned_data.get('full_name'),
                    gender=form.cleaned_data.get('gender'),
                    date_of_birth=form.cleaned_data.get('date_of_birth'),
                    mobile_number=form.cleaned_data.get('mobile_number'),
                    alternate_mobile_number=form.cleaned_data.get('alternate_mobile_number') or None,
                )
                if form.cleaned_data.get('profile_picture'):
                    update_request.profile_picture = form.cleaned_data.get('profile_picture')
                update_request.save()

                profile.is_verified_by_superuser = False
                profile.save()
                
                # Auto-send notification for update request
                Notification.objects.create(
                    user=request.user,
                    title="Profile Update Submitted",
                    message="Your admin profile update request was submitted successfully.",
                    url="/adminpanel/profile/"
                )
                
                messages.success(request, 'Profile submitted successfully! Admin will review your request soon.')
                messages.warning(request, 'Your profile is pending verification by admin. You will have full access once verified.')
                return redirect('admin_profile_edit')

            updated_profile = form.save(commit=False)
            updated_profile.is_profile_complete = True
            updated_profile.is_verified_by_superuser = False
            updated_profile.save()
            
            # Auto-send notification for direct save
            Notification.objects.create(
                user=request.user,
                title="Profile Saved",
                message="Your admin profile has been completed and saved successfully.",
                url="/adminpanel/profile/"
            )
            
            messages.success(request, 'Profile submitted successfully! Admin will review your request soon.')
            messages.warning(request, 'Your profile is pending verification by admin. You will have full access once verified.')
            return redirect('admin_profile_edit')
    else:
        form = AdminProfileEditForm(instance=profile)

    return render(request, 'admin_profile_edit.html', {'form': form, 'user': request.user})


@login_required(login_url='/api/auth/login/')
def admin_profile_delete_view(request):
    """Redirect to the unified email-confirmed account deletion flow."""
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')
    return redirect('/api/auth/delete-account/')


@login_required(login_url='/api/auth/login/')
def admin_profile_view(request):
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')
    profile = request.user.admin_profile
    return render(request, 'profile_admin.html', {'profile': profile, 'user': request.user})


@login_required(login_url='/api/auth/login/')
def admin_dashboard_view(request):
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')

    profile = request.user.admin_profile

    if not profile.is_profile_complete:
        messages.warning(request, 'Please complete your admin profile before accessing the dashboard.')
        return redirect('admin_profile_edit')

    # Get pending verification requests
    pending_requests = LawyerVerificationRequest.objects.filter(
        status='pending'
    ).select_related('lawyer', 'lawyer__user').order_by('-submitted_at')

    pending_update_requests = LawyerProfileUpdateRequest.objects.filter(
        status='PENDING'
    ).select_related('lawyer', 'lawyer__user').order_by('-submitted_at')

    # Get pending document verifications
    pending_documents = CaseDocumentVerification.objects.filter(
        status='PENDING'
    ).exclude(document__case_request__status='PENDING').select_related('document', 'document__case_request', 'document__case_request__client').order_by('-document__uploaded_at')

    pending_reports = TrustReport.objects.filter(
        status='PENDING'
    ).select_related('reporter', 'reported_client__user', 'reported_lawyer__user').order_by('-created_at')

    active_cases_count = CaseRequest.objects.filter(status='ACCEPTED').count()
    pending_case_requests_count = CaseRequest.objects.filter(
        status__in=['PENDING', 'DOCUMENTS_PENDING', 'DOCUMENTS_SUBMITTED']
    ).count()
    flagged_accounts_count = TrustReport.objects.filter(
        status='PENDING'
    ).values_list('reported_lawyer', 'reported_client').distinct().count()

    context = {
        'profile': profile,
        'user': request.user,
        'is_verified': profile.is_verified_by_superuser,
        'is_complete': profile.is_profile_complete,
        'pending_requests': pending_requests,
        'pending_count': pending_requests.count(),
        'pending_update_requests': pending_update_requests,
        'pending_update_count': pending_update_requests.count(),
        'pending_documents': pending_documents,
        'pending_documents_count': pending_documents.count(),
        'pending_reports': pending_reports,
        'pending_reports_count': pending_reports.count(),
        'active_cases_count': active_cases_count,
        'pending_case_requests_count': pending_case_requests_count,
        'flagged_accounts_count': flagged_accounts_count,
    }
    return render(request, 'admin_dashboard.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def lawyer_verification_list_view(request):
    """List all pending lawyer verification requests for admin review."""
    pending_requests = LawyerVerificationRequest.objects.filter(
        status='pending'
    ).select_related('lawyer', 'lawyer__user').order_by('-submitted_at')

    pending_update_requests = LawyerProfileUpdateRequest.objects.filter(
        status='PENDING'
    ).select_related('lawyer', 'lawyer__user').order_by('-submitted_at')

    context = {
        'pending_requests': pending_requests,
        'pending_count': pending_requests.count(),
        'pending_update_requests': pending_update_requests,
        'pending_update_count': pending_update_requests.count(),
        'user': request.user,
    }
    return render(request, 'lawyer_verification_list.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def trust_report_list_view(request):
    """List all pending trust reports for admin review."""
    pending_reports = TrustReport.objects.filter(
        status='PENDING'
    ).select_related('reporter', 'reported_client__user', 'reported_lawyer__user').order_by('-created_at')

    return render(request, 'trust_report_list.html', {
        'pending_reports': pending_reports,
        'pending_reports_count': pending_reports.count(),
        'user': request.user,
    })


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def trust_report_detail_view(request, report_id):
    """Show and take action on a specific trust report."""
    report = get_object_or_404(TrustReport, id=report_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('admin_notes', '').strip()

        report.admin_notes = notes
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()

        if action == 'approve':
            report.status = 'APPROVED'
            Notification.objects.create(
                user=report.reporter,
                title='Report approved',
                message=f'Your report against {report.target_name} has been reviewed and marked approved.',
                url='/adminpanel/reports/'
            )
        elif action == 'warn':
            report.status = 'WARNED'
            Notification.objects.create(
                user=report.reporter,
                title='Report action taken',
                message=f'Your report against {report.target_name} has been reviewed and the reported user has been warned.',
                url='/adminpanel/reports/'
            )
        elif action == 'ban':
            report.status = 'BANNED'
            if report.reported_lawyer:
                report.reported_lawyer.soft_delete()
                Notification.objects.create(
                    user=report.reported_lawyer.user,
                    title='Account banned',
                    message='Your account has been banned after review of a trust report.',
                    url='/'
                )
            if report.reported_client:
                report.reported_client.soft_delete()
                Notification.objects.create(
                    user=report.reported_client.user,
                    title='Account banned',
                    message='Your account has been banned after review of a trust report.',
                    url='/'
                )
            Notification.objects.create(
                user=report.reporter,
                title='Report action taken',
                message=f'Your report against {report.target_name} resulted in a ban.',
                url='/adminpanel/reports/'
            )
        elif action == 'reject':
            report.status = 'REJECTED'
            Notification.objects.create(
                user=report.reporter,
                title='Report rejected',
                message=f'Your report against {report.target_name} has been rejected by the admin team.',
                url='/adminpanel/reports/'
            )

        report.save()

        # Send action notification emails to both the reporter (client/lawyer) and the reported user (lawyer/client)
        try:
            send_report_action_to_reporter(report)
        except Exception:
            pass

        try:
            send_report_action_to_reported(report)
        except Exception:
            pass

        messages.success(request, 'Trust report updated successfully.')
        return redirect('trust_report_list')

    report.formatted_id = f"ri::{report.id:05d}"
    return render(request, 'trust_report_detail.html', {
        'report': report,
        'user': request.user,
    })


def lawyer_verification_detail_view(request, lawyer_id):
    """Show lawyer details for admin review."""
    lawyer = get_object_or_404(LawyerProfile, id=lawyer_id)
    verification_request = get_object_or_404(LawyerVerificationRequest, lawyer=lawyer)

    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')

        if action == 'approve':
            verification_request.status = 'approved'
            lawyer.verified = True
            verification_request.reviewed_by = request.user
            verification_request.notes = notes
            verification_request.reviewed_at = timezone.now()

            verification_request.save()
            lawyer.save()
            
            # Send notification to the lawyer
            Notification.objects.create(
                user=lawyer.user,
                title="Profile Verified",
                message="Congratulations! Your lawyer profile has been verified successfully by admin.",
                url="/lawyers/profile/"
            )

            messages.success(request, f'✓ {lawyer.full_name} has been verified successfully!')
            return redirect('admin_dashboard')

        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            verification_request.status = 'rejected'
            verification_request.rejection_reason = rejection_reason
            verification_request.reviewed_by = request.user
            verification_request.notes = notes
            verification_request.reviewed_at = timezone.now()

            verification_request.save()
            
            # Send notification to the lawyer
            Notification.objects.create(
                user=lawyer.user,
                title="Verification Rejected",
                message=f"Your lawyer verification request was rejected. Reason: {rejection_reason}",
                url="/lawyers/profile/edit/"
            )

            messages.warning(request, f'✗ {lawyer.full_name} verification has been rejected.')
            return redirect('admin_dashboard')

    context = {
        'lawyer': lawyer,
        'verification_request': verification_request,
        'user_obj': lawyer.user,
    }
    return render(request, 'lawyer_verification_detail.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def lawyer_update_request_detail_view(request, request_id):
    """Show a lawyer profile update request for admin review."""
    update_request = get_object_or_404(LawyerProfileUpdateRequest, id=request_id)
    lawyer = update_request.lawyer

    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')

        if action == 'approve':
            lawyer.full_name = update_request.full_name or lawyer.full_name
            lawyer.gender = update_request.gender or lawyer.gender
            lawyer.date_of_birth = update_request.date_of_birth or lawyer.date_of_birth
            lawyer.bar_registration_number = update_request.bar_registration_number or lawyer.bar_registration_number
            lawyer.state_bar_council = update_request.state_bar_council or lawyer.state_bar_council
            lawyer.years_of_experience = update_request.years_of_experience if update_request.years_of_experience is not None else lawyer.years_of_experience
            lawyer.specialization = update_request.specialization or lawyer.specialization
            lawyer.bio = update_request.bio or lawyer.bio
            lawyer.consultation_fee = update_request.consultation_fee if update_request.consultation_fee is not None else lawyer.consultation_fee
            lawyer.office_city = update_request.office_city or lawyer.office_city
            lawyer.mobile_number = update_request.mobile_number or lawyer.mobile_number
            lawyer.alternate_mobile_number = update_request.alternate_mobile_number or lawyer.alternate_mobile_number

            if update_request.profile_picture:
                lawyer.profile_picture = update_request.profile_picture

            lawyer.save()

            update_request.status = 'APPROVED'
            update_request.reviewed_at = timezone.now()
            update_request.admin_notes = notes
            update_request.save()
            
            # Send notification to the lawyer
            Notification.objects.create(
                user=lawyer.user,
                title="Profile Update Approved",
                message="Your lawyer profile update request has been approved and applied.",
                url="/lawyers/profile/"
            )

            messages.success(request, f'✓ {lawyer.full_name} profile update approved and applied.')
            return redirect('admin_dashboard')

        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            update_request.status = 'REJECTED'
            update_request.reviewed_at = timezone.now()
            update_request.admin_notes = notes or rejection_reason
            update_request.save()
            
            # Send notification to the lawyer
            Notification.objects.create(
                user=lawyer.user,
                title="Profile Update Rejected",
                message=f"Your profile update request was rejected. Reason: {notes or rejection_reason}",
                url="/lawyers/profile/edit/"
            )

            messages.warning(request, f'✗ {lawyer.full_name} profile update rejected.')
            return redirect('admin_dashboard')

    context = {
        'lawyer': lawyer,
        'update_request': update_request,
        'user_obj': lawyer.user,
    }
    return render(request, 'lawyer_update_request_detail.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def case_documents_verification_list_view(request):
    """List all pending case documents for verification."""
    # Get all pending documents
    pending_verifications = CaseDocumentVerification.objects.filter(
        status='PENDING'
    ).exclude(document__case_request__status='PENDING').select_related('document', 'document__case_request', 'document__case_request__client', 'document__case_request__lawyer').order_by('-document__uploaded_at')

    # Group by case request
    cases_with_pending_docs = {}
    for verification in pending_verifications:
        case_id = verification.document.case_request.id
        if case_id not in cases_with_pending_docs:
            cases_with_pending_docs[case_id] = {
                'case_request': verification.document.case_request,
                'documents': []
            }
        cases_with_pending_docs[case_id]['documents'].append(verification.document)

    context = {
        'cases_with_pending_docs': cases_with_pending_docs.values(),
        'total_pending': len(pending_verifications),
        'user': request.user,
    }
    return render(request, 'case_documents_verification_list.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def pending_cases_list_view(request):
    """List all cases accepted by lawyers for admin review."""
    query = request.GET.get('q', '').strip()
    accepted_cases = CaseRequest.objects.filter(
        status='ACCEPTED'
    ).select_related('client', 'client__user', 'lawyer', 'lawyer__user').order_by('-updated_at')

    if query:
        if query.isdigit():
            accepted_cases = accepted_cases.filter(
                Q(id=query) | Q(client__id=query)
            )
        else:
            accepted_cases = accepted_cases.none()

    context = {
        'accepted_cases': accepted_cases,
        'query': query,
        'count': accepted_cases.count(),
        'user': request.user,
    }
    return render(request, 'pending_cases_list.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def case_document_verify_view(request, document_id):
    """Verify individual case documents - all documents MUST be verified before lawyer can proceed."""
    document = get_object_or_404(CaseDocument, id=document_id)
    case_request = document.case_request
    
    # Get or create verification record
    verification, created = CaseDocumentVerification.objects.get_or_create(document=document)

    if request.method == 'POST':
        form = DocumentVerificationForm(request.POST, instance=verification)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.verified_by = request.user
            
            if verification.status == 'VERIFIED':
                verification.verified_at = timezone.now()
                verification.rejection_reason = None
            elif verification.status == 'REJECTED':
                verification.verified_at = timezone.now()
                # If document is rejected, check rejection reason is provided
                if not verification.rejection_reason or not verification.rejection_reason.strip():
                    form.add_error('rejection_reason', 'Rejection reason is required when rejecting a document.')
                    context = {
                        'form': form,
                        'document': document,
                        'case_request': case_request,
                        'verification': verification,
                        'user': request.user,
                    }
                    return render(request, 'case_document_verify.html', context)
            
            verification.save()

            # Auto-send notification to the client regarding individual document status
            if verification.status == 'VERIFIED':
                Notification.objects.create(
                    user=case_request.client.user,
                    title="Document Approved",
                    message=f"Your document '{document.document_type}' has been verified and approved by admin.",
                    url="/cases/"
                )
            elif verification.status == 'REJECTED':
                Notification.objects.create(
                    user=case_request.client.user,
                    title="Document Rejected",
                    message=f"Your document '{document.document_type}' was rejected. Reason: {verification.rejection_reason}",
                    url="/cases/"
                )

            # Check if all documents for this case are verified
            all_verified = CaseDocumentVerification.objects.filter(
                document__case_request=case_request,
                status='VERIFIED'
            ).count() == CaseDocument.objects.filter(
                case_request=case_request
            ).count()

            # Check if any documents are rejected
            any_rejected = CaseDocumentVerification.objects.filter(
                document__case_request=case_request,
                status='REJECTED'
            ).exists()

            if any_rejected:
                # If any documents are rejected, update case status to show issues
                case_request.status = 'DOCUMENTS_SUBMITTED'
                case_request.save()
                messages.warning(request, f"Document marked as rejected. Client must resubmit or fix the issue: {verification.rejection_reason}")
            elif all_verified:
                # Only update to DOCUMENTS_VERIFIED if ALL are verified
                case_request.status = 'DOCUMENTS_VERIFIED'
                case_request.workflow_stage = 'LAWYER_ASSIGNED'
                case_request.workflow_stage_updated_at = timezone.now()
                case_request.documents_verified_at = timezone.now()
                case_request.save()

                # Notify lawyer
                Notification.objects.create(
                    user=case_request.lawyer.user,
                    title='Case documents verified - Ready to accept',
                    message=f'All documents for case from {case_request.client.get_full_name()} have been verified by admin. You can now accept and work on the case.',
                    url=f'/lawyers/case/{case_request.id}/accept/'
                )

                messages.success(request, "✓ Document verified! All documents are now verified. Case is ready for lawyer to accept.")
            else:
                pending = CaseDocument.objects.filter(
                    case_request=case_request
                ).exclude(
                    casedocumentverification__status__in=['VERIFIED', 'REJECTED']
                ).count()
                messages.info(request, f"Document verification status updated. {pending} document(s) still pending verification.")

            return redirect('case_documents_verification_list')
    else:
        form = DocumentVerificationForm(instance=verification)

    # Get verification statistics
    total_docs = CaseDocument.objects.filter(case_request=case_request).count()
    verified_docs = CaseDocumentVerification.objects.filter(
        document__case_request=case_request,
        status='VERIFIED'
    ).count()
    rejected_docs = CaseDocumentVerification.objects.filter(
        document__case_request=case_request,
        status='REJECTED'
    ).count()
    pending_docs = total_docs - verified_docs - rejected_docs

    context = {
        'form': form,
        'document': document,
        'case_request': case_request,
        'verification': verification,
        'user': request.user,
        'total_docs': total_docs,
        'verified_docs': verified_docs,
        'rejected_docs': rejected_docs,
        'pending_docs': pending_docs,
    }
    return render(request, 'case_document_verify.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
def case_details_for_admin(request, case_request_id):
    """Show all documents for a specific case for admin review."""
    case_request = get_object_or_404(CaseRequest, id=case_request_id)
    documents = CaseDocument.objects.filter(case_request=case_request).prefetch_related('casedocumentverification')
    
    # Count verification statistics
    total_docs = documents.count()
    verified_docs = sum(1 for doc in documents if hasattr(doc, 'casedocumentverification') and doc.casedocumentverification.status == 'VERIFIED')
    rejected_docs = sum(1 for doc in documents if hasattr(doc, 'casedocumentverification') and doc.casedocumentverification.status == 'REJECTED')
    pending_docs = total_docs - verified_docs - rejected_docs
    
    # Determine if all documents can be verified
    all_verified = verified_docs == total_docs and total_docs > 0
    any_rejected = rejected_docs > 0

    context = {
        'case_request': case_request,
        'documents': documents,
        'total_docs': total_docs,
        'verified_docs': verified_docs,
        'rejected_docs': rejected_docs,
        'pending_docs': pending_docs,
        'all_verified': all_verified,
        'any_rejected': any_rejected,
        'user': request.user,
    }
    return render(request, 'case_details_for_admin.html', context)
