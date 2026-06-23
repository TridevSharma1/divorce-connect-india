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
