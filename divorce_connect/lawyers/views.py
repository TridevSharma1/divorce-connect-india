from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required(login_url='/api/auth/login/')
def lawyer_profile_view(request):
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'profile_lawyer.html')


@login_required(login_url='/api/auth/login/')
def lawyer_dashboard_view(request):
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'lawyer_dashboard.html')

# Add this to your existing lawyers/views.py
def lawyer_section_view(request):
    """Public marketplace page where clients search for lawyers."""
    return render(request, 'lawyers_section.html')

# Add this near your other lawyer views in lawyers/views.py
@login_required(login_url='/api/auth/login/')
def earning_dashboard_view(request):
    """Secure financial dashboard for lawyers."""
    # Ensure only lawyers can access this
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'earning_dashboard.html')

# Add this in lawyers/views.py
@login_required(login_url='/api/auth/login/')
def case_order_view(request):
    """Inbox for lawyers to view incoming consultation requests."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'case_order.html')

# Add this in lawyers/views.py
@login_required(login_url='/api/auth/login/')
def case_status_view(request):
    """Operational CRM view for lawyers to manage active clients."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'case_status.html')

# Add this in lawyers/views.py
@login_required(login_url='/api/auth/login/')
def account_settings_view(request):
    """Backend settings for lawyer availability, security, and notifications."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'account_settings.html')

# Add this in lawyers/views.py
@login_required(login_url='/api/auth/login/')
def billing_payment_view(request):
    """Secure page for lawyer payouts, taxes, and invoices."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'billing_payment.html')

# Add this in lawyers/views.py
@login_required(login_url='/api/auth/login/')
def support_lawyer_view(request):
    """Priority help center and ticketing for lawyers."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'support_lawyer.html')

# Add this in lawyers/views.py
@login_required(login_url='/api/auth/login/')
def report_client_view(request):
    """Trust and safety page for lawyers to report abusive clients."""
    if not hasattr(request.user, 'lawyer_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'report_client.html')