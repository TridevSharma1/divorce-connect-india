from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page_view, name='landing_page'),
    path('dashboard/', views.client_dashboard_view, name='client_dashboard'),
    
    # The new counseling section
    path('counseling/', views.counseling_view, name='counseling'),
    # The new about section
    path('about/', views.about_view, name='about'),
    # The new support section
    path('support/', views.support_view, name='support'),
    # The new contact section
    path('contact/', views.contact_view, name='contact'),
    # Inside your urlpatterns list, add:
    path('report/', views.report_lawyer_view, name='report_lawyer'),
    # Add these inside your urlpatterns list
    path('profile/edit/', views.edit_profile_client_view, name='client_profile'),
    path('profile/delete/', views.delete_client_account_view, name='client_delete_account'),
]