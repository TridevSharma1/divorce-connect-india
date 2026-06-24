from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from adminpanel.forms import AdminProfileEditForm
from adminpanel.models import LawyerVerificationRequest
from lawyers.models import LawyerProfile


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
            form.save(commit=False)
            profile.is_profile_complete = True
            profile.save()
            messages.success(request, 'Profile submitted successfully! Awaiting superuser verification.')
            return redirect('/adminpanel/dashboard/')
    else:
        form = AdminProfileEditForm(instance=profile)

    return render(request, 'admin_profile_edit.html', {'form': form})


@login_required(login_url='/api/auth/login/')
def admin_profile_view(request):
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')
    profile = request.user.admin_profile
    return render(request, 'profile_admin.html', {'profile': profile})


@login_required(login_url='/api/auth/login/')
def admin_dashboard_view(request):
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')

    profile = request.user.admin_profile

    # Get pending verification requests
    pending_requests = LawyerVerificationRequest.objects.filter(
        status='pending'
    ).select_related('lawyer', 'lawyer__user').order_by('-submitted_at')

    context = {
        'profile': profile,
        'is_verified': profile.is_verified_by_superuser,
        'is_complete': profile.is_profile_complete,
        'pending_requests': pending_requests,
        'pending_count': pending_requests.count()
    }
    return render(request, 'admin_dashboard.html', context)


@login_required(login_url='/api/auth/login/')
@user_passes_test(is_admin_staff, login_url='/api/auth/login/')
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

            messages.success(request, f'✓ {lawyer.full_name} has been verified successfully!')
            return redirect('/adminpanel/dashboard/')

        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            verification_request.status = 'rejected'
            verification_request.rejection_reason = rejection_reason
            verification_request.reviewed_by = request.user
            verification_request.notes = notes
            verification_request.reviewed_at = timezone.now()

            verification_request.save()

            messages.warning(request, f'✗ {lawyer.full_name} verification has been rejected.')
            return redirect('/adminpanel/dashboard/')

    context = {
        'lawyer': lawyer,
        'verification_request': verification_request,
        'user_obj': lawyer.user
    }
    return render(request, 'lawyer_verification_detail.html', context)
