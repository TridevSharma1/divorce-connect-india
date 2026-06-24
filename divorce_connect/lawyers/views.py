from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from lawyers.forms import LawyerProfileEditForm
from lawyers.models import LawyerProfile, LawyerProfileUpdateRequest
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
    return render(request, 'lawyer_detail.html', {'lawyer': lawyer})

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
            user.delete() # Automatically cascades to LawyerProfile and UpdateRequests
            messages.success(request, "Your practice account has been permanently closed.")
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
    context = {
        'profile': profile,
        'is_verified': profile.verified,
        'is_complete': profile.is_profile_complete
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
    return render(request, 'case_order.html')

@login_required(login_url='/api/auth/login/')
@require_verified_profile(profile_type='lawyer')
def case_status_view(request):
    """Operational CRM view for lawyers to manage active clients."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'case_status.html')

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
    return render(request, 'report_client.html')