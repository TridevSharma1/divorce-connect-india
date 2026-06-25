from django.urls import path
from . import views
from lawyers import views as lawyer_views

urlpatterns = [
    path('', views.landing_page_view, name='landing_page'),
    path('dashboard/', views.client_dashboard_view, name='client_dashboard'),
    path('cases/', views.client_cases_view, name='client_cases'),
    
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
    
    # Case Document Routes
    path('cases/<int:case_request_id>/upload-documents/', lawyer_views.case_document_upload_view, name='case_document_upload'),
    path('cases/<int:case_request_id>/documents-status/', lawyer_views.case_documents_status_view, name='case_documents_status'),
]