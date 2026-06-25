from django.urls import path
from . import views

urlpatterns = [
    # Public Marketplace Routes
    path('', views.lawyer_section_view, name='lawyers_section'),
    path('<int:lawyer_id>/', views.lawyer_detail_view, name='lawyer_detail'),

    # Private Lawyer Dashboard & Core Routes
    path('dashboard/', views.lawyer_dashboard_view, name='lawyer_dashboard'),
    path('profile/', views.lawyer_profile_view, name='lawyer_profile'),
    
    # Profile Editing & Deletion (RUD Operations)
    path('profile/edit/', views.lawyer_profile_edit_view, name='lawyer_profile_edit'),
    path('profile/delete/', views.lawyer_delete_account_view, name='lawyer_delete_account'),

    # Operational Pages (Inbox, CRM, Financials)
    path('orders/', views.case_order_view, name='lawyer_case_orders'),
    path('requests/<int:request_id>/accept/', views.case_request_accept_view, name='case_request_accept'),
    path('requests/<int:request_id>/reject/', views.case_request_reject_view, name='case_request_reject'),
    path('status/', views.case_status_view, name='lawyer_case_status'),
    path('earnings/', views.earning_dashboard_view, name='lawyer_earnings'),
    path('billing/', views.billing_payment_view, name='lawyer_billing'),

    # Case Document Routes
    path('case/<int:case_request_id>/view-documents/', views.lawyer_view_case_documents, name='lawyer_view_case_documents'),
    path('case/<int:case_request_id>/accept/', views.lawyer_accept_case_view, name='lawyer_accept_case'),
    path('case/<int:case_request_id>/advance-stage/', views.lawyer_advance_case_stage_view, name='lawyer_advance_case_stage'),

    # Settings & Support
    path('settings/', views.account_settings_view, name='lawyer_settings'),
    path('support/', views.support_lawyer_view, name='lawyer_support'),
    path('report-client/', views.report_client_view, name='lawyer_report_client'),
]