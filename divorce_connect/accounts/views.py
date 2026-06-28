from django.shortcuts import render, redirect
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.core.exceptions import ValidationError
from .forms import BaseUserAuthenticationForm, BaseUserRegistrationForm
from .models import BaseUser, OTPCode, DeleteAccountToken
from clients.models import ClientProfile
from lawyers.models import LawyerProfile
from adminpanel.models import AdminPanelProfile
from utils.email_utils import (
    send_otp_email,
    send_password_reset_otp_email,
    send_register_otp_email,
    send_registration_email,
    send_welcome_back_email,
    send_logout_email,
    send_delete_account_email,
)


# ──────────────────────────────────────────────
#  FORGOT PASSWORD  →  OTP  →  NEW PASSWORD
# ──────────────────────────────────────────────

def forgot_password_view(request):
    """Collect the user's email and send a reset verification code."""
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'forgot_password.html')

        try:
            user = BaseUser.objects.get(email__iexact=email)
        except BaseUser.DoesNotExist:
            messages.error(request, 'No account was found with that email address.')
            return render(request, 'forgot_password.html')

        request.session['otp_user_id'] = user.pk
        request.session['otp_user_email'] = user.email
        request.session['otp_purpose'] = 'password_reset'

        otp = OTPCode.generate_for_user(user)
        try:
            send_password_reset_otp_email(user, otp.code)
        except Exception:
            pass

        messages.success(request, 'A verification code has been sent to your email.')
        return redirect('verify_otp')

    return render(request, 'forgot_password.html')


def reset_password_view(request):
    """Allow the user to choose a new password after OTP verification."""
    user_id = request.session.get('password_reset_user_id')
    if not user_id:
        return redirect('forgot_password')

    try:
        user = BaseUser.objects.get(pk=user_id)
    except BaseUser.DoesNotExist:
        request.session.pop('password_reset_user_id', None)
        return redirect('forgot_password')

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not new_password or not confirm_password:
            messages.error(request, 'Please enter and confirm your new password.')
        elif new_password != confirm_password:
            messages.error(request, 'The two password fields did not match.')
        else:
            try:
                validate_password(new_password, user=user)
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
                return render(request, 'reset_password.html')

            user.set_password(new_password)
            user.save()
            request.session.pop('password_reset_user_id', None)
            messages.success(request, 'Your password has been changed successfully. Please sign in with your new password.')
            return redirect('login')

    return render(request, 'reset_password.html')


# ──────────────────────────────────────────────
#  LOGIN  →  OTP  →  WELCOME BACK
# ──────────────────────────────────────────────

def login_view(request):
    """Step 1 of login: validate credentials, then route to OTP page."""
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)

    if request.method == 'POST':
        form = BaseUserAuthenticationForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            # Stash user info in session for OTP step
            request.session['otp_user_id'] = user.pk
            request.session['otp_user_email'] = user.email
            request.session['otp_purpose'] = 'login'

            otp = OTPCode.generate_for_user(user)
            try:
                send_otp_email(user, otp.code)
            except Exception:
                pass

            return redirect('verify_otp')
    else:
        form = BaseUserAuthenticationForm()

    return render(request, 'login.html', {'form': form})


def verify_otp_view(request):
    """Step 2 of login: verify OTP then log user in + send welcome-back email."""
    user_id = request.session.get('otp_user_id')
    user_email = request.session.get('otp_user_email', '')
    purpose = request.session.get('otp_purpose', 'login')

    if not user_id or purpose not in ['login', 'password_reset']:
        return redirect('login')

    try:
        user = BaseUser.objects.get(pk=user_id)
    except BaseUser.DoesNotExist:
        messages.error(request, 'Session expired. Please log in again.')
        return redirect('login')

    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()

        otp_obj = OTPCode.objects.filter(
            user=user, is_used=False, code=entered
        ).order_by('-created_at').first()

        if otp_obj and not otp_obj.is_expired():
            otp_obj.is_used = True
            otp_obj.save()
            # Clear OTP session keys
            for key in ['otp_user_id', 'otp_user_email', 'otp_purpose']:
                request.session.pop(key, None)

            if purpose == 'password_reset':
                request.session['password_reset_user_id'] = user.pk
                messages.success(request, 'Verification successful. Please create a new password.')
                return redirect('reset_password')

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Send "Welcome Back" email
            try:
                send_welcome_back_email(user)
            except Exception:
                pass

            return redirect_to_dashboard(user)

        elif otp_obj and otp_obj.is_expired():
            messages.error(request, 'This OTP has expired. Please log in again to receive a new one.')
            return redirect('login')
        else:
            messages.error(request, 'Invalid OTP. Please check the code and try again.')

    return render(request, 'verify_otp.html', {'email': user_email})


# ──────────────────────────────────────────────
#  REGISTER  →  OTP  →  WELCOME EMAIL  →  DASHBOARD
# ──────────────────────────────────────────────

def register_view(request):
    """Step 1 of registration: collect details, send OTP, redirect to verify page."""
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)

    if request.method == 'POST':
        form = BaseUserRegistrationForm(request.POST)
        if form.is_valid():
            role       = form.cleaned_data['role']
            email      = form.cleaned_data['email']
            password   = form.cleaned_data['password1']
            first_name = form.cleaned_data['first_name']
            last_name  = form.cleaned_data['last_name']

            # Don't create the user yet — stash data in session for OTP verification
            request.session['reg_email']      = email
            request.session['reg_password']   = password
            request.session['reg_first_name'] = first_name
            request.session['reg_last_name']  = last_name
            request.session['reg_role']       = role

            # Create a temporary user object to generate OTP (not saved)
            # We need a saved user to use OTPCode FK — so create a minimal
            # "pending" user and delete if OTP fails. Use a marker on the session.
            user, created = BaseUser.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': False,   # inactive until OTP verified
                }
            )
            if created:
                user.set_password(password)
                user.save()

            otp = OTPCode.generate_for_user(user)
            try:
                send_register_otp_email(user, otp.code)
            except Exception:
                pass

            request.session['reg_user_id']    = user.pk
            request.session['otp_purpose']    = 'register'

            return redirect('verify_register_otp')
        else:
            return render(request, 'register.html', {'form': form})
    else:
        form = BaseUserRegistrationForm()

    return render(request, 'register.html', {'form': form})


def verify_register_otp_view(request):
    """Step 2 of registration: verify OTP, activate account, send welcome email."""
    user_id = request.session.get('reg_user_id')
    email   = request.session.get('reg_email', '')
    purpose = request.session.get('otp_purpose', '')

    if not user_id or purpose != 'register':
        return redirect('register')

    try:
        user = BaseUser.objects.get(pk=user_id)
    except BaseUser.DoesNotExist:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')

    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()

        otp_obj = OTPCode.objects.filter(
            user=user, is_used=False, code=entered
        ).order_by('-created_at').first()

        if otp_obj and not otp_obj.is_expired():
            otp_obj.is_used = True
            otp_obj.save()

            role       = request.session.get('reg_role', 'client')
            first_name = request.session.get('reg_first_name', '')
            last_name  = request.session.get('reg_last_name', '')

            # Activate user and create profile
            user.first_name = first_name
            user.last_name  = last_name
            user.is_active  = True
            user.save()

            # Create role-specific profile if not already done
            if role == 'client' and not hasattr(user, 'client_profile'):
                ClientProfile.objects.create(
                    user=user, first_name=first_name, last_name=last_name, mobile_number=''
                )
            elif role == 'lawyer' and not hasattr(user, 'lawyer_profile'):
                LawyerProfile.objects.create(
                    user=user, full_name=f"{first_name} {last_name}",
                    mobile_number='', bar_registration_number='PENDING', state_bar_council=''
                )
            elif role == 'admin' and not hasattr(user, 'admin_profile'):
                AdminPanelProfile.objects.create(
                    user=user, full_name=f"{first_name} {last_name}", mobile_number=''
                )

            # Clean up session
            for key in ['reg_email','reg_password','reg_first_name','reg_last_name',
                        'reg_role','reg_user_id','otp_purpose']:
                request.session.pop(key, None)

            # Send welcome registration email
            try:
                send_registration_email(user, role)
            except Exception:
                pass

            # Log the user in
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            if role == 'admin':
                return redirect('/adminpanel/profile/edit/')
            return redirect_to_dashboard(user)

        elif otp_obj and otp_obj.is_expired():
            messages.error(request, 'This OTP has expired. Please register again.')
            # Clean up inactive user
            user.delete()
            for key in ['reg_email','reg_password','reg_first_name','reg_last_name',
                        'reg_role','reg_user_id','otp_purpose']:
                request.session.pop(key, None)
            return redirect('register')
        else:
            messages.error(request, 'Invalid OTP. Please check the code sent to your email.')

    return render(request, 'verify_register_otp.html', {'email': email})


# ──────────────────────────────────────────────
#  LOGOUT
# ──────────────────────────────────────────────

def logout_view(request):
    user = request.user
    user_name = getattr(user, 'get_full_name', lambda: '')() or getattr(user, 'email', '')
    email = getattr(user, 'email', None)
    logout(request)
    if email:
        try:
            send_logout_email(user_name, email)
        except Exception:
            pass
    return redirect('/')


# ──────────────────────────────────────────────
#  DELETE ACCOUNT (all roles)
# ──────────────────────────────────────────────

@login_required(login_url='/api/auth/login/')
def request_delete_account_view(request):
    """Show the deletion form; validate entered email then send deletion link."""
    if request.method == 'POST':
        entered_email = request.POST.get('email', '').strip().lower()
        if entered_email != request.user.email.lower():
            messages.error(request, 'The email address you entered does not match your registered account email.')
            return render(request, 'request_delete_account.html')

        token_obj = DeleteAccountToken.generate_for_user(request.user)
        confirm_url = request.build_absolute_uri(
            f'/api/auth/confirm-delete/{token_obj.token}/'
        )
        try:
            send_delete_account_email(request.user, confirm_url)
        except Exception:
            pass

        messages.success(
            request,
            'A deletion confirmation link has been sent to your email. '
            'Please check your inbox and click the link within 30 minutes.'
        )
        return render(request, 'request_delete_account.html')

    return render(request, 'request_delete_account.html')


def confirm_delete_account_view(request, token):
    """Process the deletion confirmation link from the email."""
    token_obj = DeleteAccountToken.objects.filter(
        token=token, is_used=False
    ).select_related('user').first()

    if not token_obj:
        messages.error(request, 'This deletion link is invalid or has already been used.')
        return redirect('/')

    if token_obj.is_expired():
        token_obj.is_used = True
        token_obj.save()
        messages.error(request, 'This deletion link has expired. Please request account deletion again.')
        return redirect('/')

    user = token_obj.user
    token_obj.is_used = True
    token_obj.save()

    # Soft-delete the correct profile
    if hasattr(user, 'client_profile'):
        user.client_profile.soft_delete()
    elif hasattr(user, 'lawyer_profile'):
        user.lawyer_profile.soft_delete()
    elif hasattr(user, 'admin_profile'):
        user.admin_profile.soft_delete()

    # Log out if it's the same browser session
    if request.user.is_authenticated and request.user.pk == user.pk:
        logout(request)

    messages.success(request, 'Your account has been permanently deleted. We\'re sorry to see you go.')
    return redirect('/')


# ──────────────────────────────────────────────
#  HELPER
# ──────────────────────────────────────────────

def redirect_to_dashboard(user):
    """Redirect user to their role-specific dashboard."""
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
