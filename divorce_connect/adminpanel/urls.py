from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.admin_profile_view, name='admin_profile'),
    path('profile/edit/', views.admin_profile_edit_view, name='admin_profile_edit'),
    path('profile/delete/', views.admin_profile_delete_view, name='admin_profile_delete'),
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('lawyer/<int:lawyer_id>/verify/', views.lawyer_verification_detail_view, name='lawyer_verification_detail'),
]
