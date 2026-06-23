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