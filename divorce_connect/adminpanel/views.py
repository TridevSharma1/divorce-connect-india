from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required(login_url='/api/auth/login/')
def admin_profile_view(request):
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'profile_admin.html')


@login_required(login_url='/api/auth/login/')
def admin_dashboard_view(request):
    if not hasattr(request.user, 'admin_profile'):
        return redirect('/api/auth/login/')
    return render(request, 'admin_dashboard.html')
