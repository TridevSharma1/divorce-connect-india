def user_role_context(request):
    context = {
        'user_role': None,
    }
    if request.user.is_authenticated:
        if hasattr(request.user, 'client_profile'):
            context['user_role'] = 'client'
        elif hasattr(request.user, 'lawyer_profile'):
            context['user_role'] = 'lawyer'
        elif hasattr(request.user, 'admin_profile'):
            context['user_role'] = 'admin'
    return context
