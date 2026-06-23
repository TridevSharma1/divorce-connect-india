from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


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
def client_profile_view(request):
    if not hasattr(request.user, 'client_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'profile_client.html')

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