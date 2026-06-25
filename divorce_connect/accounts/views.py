from django.shortcuts import render, redirect
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from .forms import BaseUserAuthenticationForm, BaseUserRegistrationForm
from .models import BaseUser
from clients.models import ClientProfile
from lawyers.models import LawyerProfile
from adminpanel.models import AdminPanelProfile


def login_view(request):
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)

    if request.method == 'POST':
        form = BaseUserAuthenticationForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect_to_dashboard(user)
    else:
        form = BaseUserAuthenticationForm()

    return render(request, 'login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)

    if request.method == 'POST':
        form = BaseUserRegistrationForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password1']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']

            user = BaseUser.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                username=email
            )

            if role == 'client':
                ClientProfile.objects.create(
                    user=user,
                    first_name=first_name,
                    last_name=last_name,
                    mobile_number=''
                )
            elif role == 'lawyer':
                LawyerProfile.objects.create(
                    user=user,
                    full_name=f"{first_name} {last_name}",
                    mobile_number='',
                    bar_registration_number='PENDING',
                    state_bar_council=''
                )
            elif role == 'admin':
                AdminPanelProfile.objects.create(
                    user=user,
                    full_name=f"{first_name} {last_name}",
                    mobile_number=''
                )

            user = authenticate(username=email, password=password)
            if user is not None:
                login(request, user)
                if role == 'admin':
                    return redirect('/adminpanel/profile/edit/')
                return redirect_to_dashboard(user)

            return redirect('/login/')
        else:
            return render(request, 'register.html', {'form': form})
    else:
        form = BaseUserRegistrationForm()

    return render(request, 'register.html', {'form': form})


def redirect_to_dashboard(user):
    """Redirect user to their role-specific dashboard"""
    if hasattr(user, 'lawyer_profile'):
        if not user.lawyer_profile.is_profile_complete:
            return redirect('/lawyers/profile/edit/')
        return redirect('/lawyers/dashboard/')
    elif hasattr(user, 'admin_profile'):
        if not user.admin_profile.is_profile_complete:
            return redirect('/adminpanel/profile/edit/')
        return redirect('/adminpanel/dashboard/')
    elif hasattr(user, 'client_profile'):
        return redirect('/dashboard/')
    else:
        return redirect('/api/auth/register/')


def logout_view(request):
    logout(request)
    return redirect('/')
