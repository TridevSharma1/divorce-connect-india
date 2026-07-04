from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ClientProfile
from lawyers.models import LawyerProfile, CaseRequest, CaseMessage
from adminpanel.models import TrustReport
from accounts.models import Notification
from utils.email_utils import send_report_submitted_email

def landing_page_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'client_profile'):
            return redirect('/dashboard/')
        elif hasattr(request.user, 'lawyer_profile'):
            return redirect('/lawyers/dashboard/')
        elif hasattr(request.user, 'admin_profile'):
            return redirect('/adminpanel/dashboard/')
    return render(request, 'index.html')


@login_required(login_url='/api/auth/login/')
def client_dashboard_view(request):
    if not hasattr(request.user, 'client_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'client_dashboard.html')


@login_required(login_url='/api/auth/login/')
def client_cases_view(request):
    if not hasattr(request.user, 'client_profile'):
        return redirect('/api/auth/login/')

    client_profile = request.user.client_profile
    case_requests = client_profile.sent_case_requests.select_related('lawyer', 'lawyer__user').order_by('-created_at')

    return render(request, 'client_cases.html', {
        'case_requests': case_requests,
    })


@login_required(login_url='/api/auth/login/')
def client_case_detail_view(request, case_id):
    if not hasattr(request.user, 'client_profile'):
        return redirect('/api/auth/login/')

    client_profile = request.user.client_profile
    active_case = get_object_or_404(
        CaseRequest, 
        id=case_id, 
        client=client_profile
    )

    messages_list = []
    if active_case.status in ['ACCEPTED', 'COMPLETED']:
        messages_list = active_case.messages.all().select_related('sender_user')

    if request.method == 'POST' and active_case.status == 'ACCEPTED':
        message_text = request.POST.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        
        if message_text or attachment:
            CaseMessage.objects.create(
                case=active_case,
                sender_type='CLIENT',
                sender_user=request.user,
                text=message_text,
                attachment=attachment
            )
            # Notify the lawyer
            Notification.objects.create(
                user=active_case.lawyer.user,
                title='New message from your client',
                message=f'You have a new message from {client_profile.get_full_name()} regarding Case #{active_case.id}',
                url=f'/lawyers/case/{active_case.id}/detail/'
            )
        return redirect('client_case_detail', case_id=active_case.id)

    return render(request, 'client_case_detail.html', {
        'active_case': active_case,
        'messages': messages_list,
    })


@login_required(login_url='/api/auth/login/')
def edit_profile_client_view(request):
    user = request.user
    
    # Get or create the profile for this user
    profile, created = ClientProfile.objects.get_or_create(user=user)
    if not profile.custom_id:
        import random
        while True:
            candidate = f"cl:{random.randint(10000, 99999)}"
            if not ClientProfile.objects.filter(custom_id=candidate).exists():
                profile.custom_id = candidate
                profile.save(update_fields=['custom_id'])
                break

    if request.method == 'POST':
        # UPDATE operation - Mapping exactly to your custom model
        profile.first_name = request.POST.get('first_name', profile.first_name)
        profile.last_name = request.POST.get('last_name', profile.last_name)
        profile.gender = request.POST.get('gender', profile.gender)
        profile.marital_status = request.POST.get('marital_status', profile.marital_status)
        profile.mobile_number = request.POST.get('mobile_number', profile.mobile_number)
        profile.alternate_mobile_number = request.POST.get('alternate_mobile_number', profile.alternate_mobile_number)
        profile.address = request.POST.get('address', profile.address)
        profile.pincode = request.POST.get('pincode', profile.pincode)
        
        # Handle Date of Birth carefully (empty string crashes DateFields)
        dob = request.POST.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob
            
        # Handle Profile Picture
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            
        profile.save()
        
        # Auto-send notification on successful profile update
        from accounts.models import Notification
        Notification.objects.create(
            user=user,
            title="Profile Updated",
            message="Your profile has been updated successfully.",
            url="/profile/"
        )
        
        messages.success(request, "Your profile has been updated successfully.")
        return redirect('client_profile')

    # READ operation
    context = {
        'profile': profile,
    }
    return render(request, 'edit_profile_client.html', context)

@login_required(login_url='/api/auth/login/')
def delete_client_account_view(request):
    """Redirect to the unified email-confirmed account deletion flow."""
    return redirect('/api/auth/delete-account/')


# --- NEW COUNSELING VIEW ---
def counseling_view(request):
    """Page for emotional and financial support services."""
    return render(request, 'counseling.html')

# --- NEW ABOUT VIEW ---
def about_view(request):
    """About us page for brand authority and trust."""
    return render(request, 'about.html')

# --- NEW SUPPORT VIEW ---
def support_view(request):
    """Self-serve help center for users."""
    return render(request, 'support.html')

# --- NEW CONTACT VIEW ---
def contact_view(request):
    """Public contact page for general inquiries."""
    return render(request, 'contact.html')

# --- NEW REPORT VIEW ---
@login_required(login_url='/api/auth/login/')
def report_lawyer_view(request):
    """Trust and safety page for reporting professionals."""
    if not hasattr(request.user, 'client_profile'):
        return redirect('/api/auth/login/')

    current_client = request.user.client_profile
    available_lawyers = LawyerProfile.objects.filter(
        case_requests__client=current_client
    ).distinct().order_by('-rating')

    if not available_lawyers.exists():
        available_lawyers = LawyerProfile.objects.filter(
            verified=True,
            is_profile_complete=True
        ).order_by('-rating')[:50]

    if request.method == 'POST':
        lawyer_id = request.POST.get('lawyer')
        reason = request.POST.get('reason', '').strip()
        description = request.POST.get('description', '').strip()
        evidence = request.FILES.get('evidence')

        if not lawyer_id or not reason or not description:
            messages.error(request, 'Please select a lawyer and provide a reason and incident description.')
            return render(request, 'report_lawyer.html', {
                'lawyers': available_lawyers,
            })

        reported_lawyer = get_object_or_404(LawyerProfile, id=lawyer_id)
        report = TrustReport.objects.create(
            reporter=request.user,
            reported_lawyer=reported_lawyer,
            reason=reason,
            description=description,
            evidence=evidence
        )

        formatted_report_id = f"ri::{report.id:05d}"

        Notification.objects.create(
            user=request.user,
            title='Report Submitted',
            message=f'Your report against {reported_lawyer.full_name} has been received and is under review. Report ID: {formatted_report_id}',
            url='/dashboard/'
        )
        Notification.objects.create(
            user=reported_lawyer.user,
            title='A report has been filed against you',
            message=f'{current_client.get_full_name()} has submitted a report. Admin will review and take action. Report ID: {formatted_report_id}',
            url='/lawyers/dashboard/'
        )

        # Notify all admin users
        from accounts.models import BaseUser
        for admin in BaseUser.objects.filter(is_staff=True, is_active=True):
            Notification.objects.create(
                user=admin,
                title="New Trust Report Filed",
                message=f"Client {current_client.get_full_name()} reported Lawyer {reported_lawyer.full_name}. Report ID: {formatted_report_id}",
                url=f"/adminpanel/reports/{report.id}/"
            )

        # Send confirmation email to the reporting client
        try:
            send_report_submitted_email(
                reporter_name=current_client.get_full_name(),
                reporter_email=request.user.email,
                reported_name=reported_lawyer.full_name,
                report_reason=reason,
                report_id=formatted_report_id,
            )
        except Exception:
            pass

        if reported_lawyer.report_count >= 3:
            messages.warning(request, 'This lawyer now has 3 or more reports and is eligible for ban review by the admin.')

        messages.success(request, 'Your report has been submitted successfully. Thank you for keeping the community safe.')
        return redirect('client_dashboard')

    return render(request, 'report_lawyer.html', {
        'lawyers': available_lawyers,
    })