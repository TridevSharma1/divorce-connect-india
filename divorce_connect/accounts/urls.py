from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    # Here is your newly moved client profile route!
    path('profile/client/', views.edit_profile_client_view, name='edit_profile_client'),
    
    # Placeholder routes for the next steps
    path('profile/lawyer/', views.edit_profile_lawyer_view, name='edit_profile_lawyer'),
    path('profile/admin/', views.edit_profile_admin_view, name='edit_profile_admin'),
]