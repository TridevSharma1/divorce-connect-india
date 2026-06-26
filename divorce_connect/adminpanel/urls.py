from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.admin_profile_view, name='admin_profile'),
    path('profile/edit/', views.admin_profile_edit_view, name='admin_profile_edit'),
    path('profile/delete/', views.admin_profile_delete_view, name='admin_profile_delete'),
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('lawyers/verify/', views.lawyer_verification_list_view, name='lawyer_verification_list'),
    path('lawyer/<int:lawyer_id>/verify/', views.lawyer_verification_detail_view, name='lawyer_verification_detail'),
    path('lawyer/update-request/<int:request_id>/', views.lawyer_update_request_detail_view, name='lawyer_update_request_detail'),
    
    # Case Document Verification Routes
    path('documents/verify/', views.case_documents_verification_list_view, name='case_documents_verification_list'),
    path('document/<int:document_id>/verify/', views.case_document_verify_view, name='case_document_verify'),
    path('case/<int:case_request_id>/details/', views.case_details_for_admin, name='case_details_for_admin'),
    path('reports/', views.trust_report_list_view, name='trust_report_list'),
    path('reports/<int:report_id>/', views.trust_report_detail_view, name='trust_report_detail'),
]
