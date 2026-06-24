from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from lawyers.forms import LawyerProfileEditForm
from lawyers.models import LawyerProfile
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
    """Profile edit view - for completing profile after registration."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')

    profile = request.user.lawyer_profile

    if request.method == 'POST':
        form = LawyerProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save(commit=False)
            profile.is_profile_complete = True
            profile.save()

            # Create or update verification request
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