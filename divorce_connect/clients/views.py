from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ClientProfile

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
def edit_profile_client_view(request):
    user = request.user
    
    # Get or create the profile for this user
    profile, created = ClientProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        # UPDATE operation - Mapping exactly to your custom model
        profile.first_name = request.POST.get('first_name', profile.first_name)
        profile.last_name = request.POST.get('last_name', profile.last_name)
        profile.gender = request.POST.get('gender', profile.gender)
        profile.marital_status = request.POST.get('marital_status', profile.marital_status)
        profile.mobile_number = request.POST.get('mobile_number', profile.mobile_number)
        profile.alternate_mobile_number = request.POST.get('alternate_mobile_number', profile.alternate_mobile_number)
        
        # Handle Date of Birth carefully (empty string crashes DateFields)
        dob = request.POST.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob
            
        # Handle Profile Picture
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            
        profile.save()
        messages.success(request, "Your profile has been updated successfully.")
        return redirect('client_profile')

    # READ operation
    context = {
        'profile': profile,
    }
    return render(request, 'edit_profile_client.html', context)

@login_required(login_url='/api/auth/login/')
def delete_client_account_view(request):
    if request.method == 'POST':
        user = request.user
        user.delete() # This deletes the BaseUser and cascades to ClientProfile automatically
        messages.success(request, "Your account has been permanently deleted.")
        return redirect('landing_page')
    return redirect('client_profile')


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
    return render(request, 'report_lawyer.html')