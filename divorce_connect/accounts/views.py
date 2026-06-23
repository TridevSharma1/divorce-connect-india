from django.shortcuts import render


def login_view(request):
    return render(request, 'login.html')


def register_view(request):
    return render(request, 'register.html')
from django.shortcuts import render

def login_view(request):
    return render(request, 'login.html')

def register_view(request):
    return render(request, 'register.html')

# Here is your moved client profile view!
def edit_profile_client_view(request):
    return render(request, 'profile_client.html')

# Placeholders for the next two steps
def edit_profile_lawyer_view(request):
    return render(request, 'profile_lawyer.html')

def edit_profile_admin_view(request):
    return render(request, 'profile_admin.html')