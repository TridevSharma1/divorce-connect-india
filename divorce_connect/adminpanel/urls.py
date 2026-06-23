from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.admin_profile_view, name='admin_profile'),
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
]
