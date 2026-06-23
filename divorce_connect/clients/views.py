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
