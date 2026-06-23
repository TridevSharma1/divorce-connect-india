from django.shortcuts import render


def edit_profile_admin_view(request):
    return render(request, 'profile_admin.html')
