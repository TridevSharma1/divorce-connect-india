from django.shortcuts import render, redirect
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from .forms import BaseUserAuthenticationForm, BaseUserCreationForm
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
        role = request.POST.get('role')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        confirm_password = request.POST.get('confirm_password')

        errors = {}

        if not role:
            errors['role'] = 'Please select a role'
        if not email:
            errors['email'] = 'Email is required'
        elif BaseUser.objects.filter(email=email).exists():
            errors['email'] = 'Email already registered'
        if not password:
            errors['password'] = 'Password is required'
        if password != confirm_password:
            errors['confirm_password'] = 'Passwords do not match'
        if len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters'
        if not first_name:
            errors['first_name'] = 'First name is required'
        if not last_name:
            errors['last_name'] = 'Last name is required'

        if errors:
            return render(request, 'register.html', {
                'errors': errors,
                'form_data': request.POST
            })

        # Create user
        user = BaseUser.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            username=email
        )

        # Create profile based on role
        if role == 'client':
            ClientProfile.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                mobile_number='+91'
            )
        elif role == 'lawyer':
            LawyerProfile.objects.create(
                user=user,
                full_name=f"{first_name} {last_name}",
                mobile_number='+91',
                bar_registration_number=f"BAR-{user.id}",
                state_bar_council="Not Specified"
            )
        elif role == 'admin':
            AdminPanelProfile.objects.create(
                user=user,
                full_name=f"{first_name} {last_name}",
                mobile_number='+91'
            )

        # Log user in
        user = authenticate(username=email, password=password)
        login(request, user)
        return redirect_to_dashboard(user)

    return render(request, 'register.html')


def redirect_to_dashboard(user):
    """Redirect user to their role-specific dashboard"""
    if hasattr(user, 'client_profile'):
        return redirect('/dashboard/')
    elif hasattr(user, 'lawyer_profile'):
        return redirect('/lawyers/dashboard/')
    elif hasattr(user, 'admin_profile'):
        return redirect('/adminpanel/dashboard/')
    else:
        return redirect('/api/auth/register/')


def logout_view(request):
    logout(request)
    return redirect('/')
