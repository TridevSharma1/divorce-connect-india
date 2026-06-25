def user_role_context(request):
    context = {
        'user_role': None,
        'notifications': [],
        'unread_notifications_count': 0,
    }
    if request.user.is_authenticated:
        if hasattr(request.user, 'admin_profile'):
            context['user_role'] = 'admin'
        elif hasattr(request.user, 'lawyer_profile'):
            context['user_role'] = 'lawyer'
        elif hasattr(request.user, 'client_profile'):
            context['user_role'] = 'client'

        context['notifications'] = request.user.notifications.all()[:6]
        context['unread_notifications_count'] = request.user.notifications.filter(is_read=False).count()
    return context
