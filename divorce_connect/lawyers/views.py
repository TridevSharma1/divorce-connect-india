from django.shortcuts import render


def edit_profile_lawyer_view(request):
    return render(request, 'profile_lawyer.html')
