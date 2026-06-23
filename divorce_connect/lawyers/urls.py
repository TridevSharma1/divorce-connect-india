from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.lawyer_profile_view, name='lawyer_profile'),
    path('dashboard/', views.lawyer_dashboard_view, name='lawyer_dashboard'),
]
