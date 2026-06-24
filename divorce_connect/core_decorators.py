from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def require_verified_profile(profile_type='lawyer'):
    """
    Decorator to check if user has completed and been verified for their profile.
    Redirects to profile edit if not complete, or profile view if not verified.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('/api/auth/login/')

            if profile_type == 'lawyer':
                if not hasattr(request.user, 'lawyer_profile'):
                    return redirect('/api/auth/login/')
                profile = request.user.lawyer_profile

                if not profile.is_profile_complete:
                    messages.warning(request, 'Please complete your profile to access this feature.')
                    return redirect('/lawyers/profile/edit/')

                if not profile.verified:
                    messages.warning(request, 'Your profile is pending verification by admin. You will have full access once verified.')
                    return redirect('/lawyers/dashboard/')

            elif profile_type == 'admin':
                if not hasattr(request.user, 'admin_profile'):
                    return redirect('/api/auth/login/')
                profile = request.user.admin_profile

                if not profile.is_profile_complete:
                    messages.warning(request, 'Please complete your profile to access this feature.')
                    return redirect('/adminpanel/profile/edit/')

                if not profile.is_verified_by_superuser:
                    messages.warning(request, 'Your profile is pending verification by superuser. You will have full access once verified.')
                    return redirect('/adminpanel/dashboard/')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
