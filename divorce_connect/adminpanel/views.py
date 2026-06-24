from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from adminpanel.forms import AdminProfileEditForm
from adminpanel.models import LawyerVerificationRequest, AdminPanelProfileUpdateRequest
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
                messages.success(request, 'Profile update request submitted. Your admin access is paused until superuser approves the updated profile.')
                return redirect('admin_dashboard')

            updated_profile = form.save(commit=False)
            updated_profile.is_profile_complete = True
            updated_profile.is_verified_by_superuser = False
            updated_profile.save()
            messages.success(request, 'Profile submitted successfully! Your admin access is paused until superuser verifies your updated profile.')
            return redirect('admin_dashboard')
    else:
        form = AdminProfileEditForm(instance=profile)

    return render(request, 'admin_profile_edit.html', {'form': form, 'user': request.user})


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

    context = {
        'profile': profile,
        'user': request.user,
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
            return redirect('admin_dashboard')

        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            verification_request.status = 'rejected'
            verification_request.rejection_reason = rejection_reason
            verification_request.reviewed_by = request.user
            verification_request.notes = notes
            verification_request.reviewed_at = timezone.now()

            verification_request.save()

            messages.warning(request, f'✗ {lawyer.full_name} verification has been rejected.')
            return redirect('admin_dashboard')

    context = {
        'lawyer': lawyer,
        'verification_request': verification_request,
        'user_obj': lawyer.user
    }
    return render(request, 'lawyer_verification_detail.html', context)
