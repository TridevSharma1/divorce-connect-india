from django.urls import path
from . import views

urlpatterns = [
    # Your existing private routes
    path('profile/', views.lawyer_profile_view, name='lawyer_profile'),
    path('dashboard/', views.lawyer_dashboard_view, name='lawyer_dashboard'),
    # The public marketplace section
    path('', views.lawyer_section_view, name='lawyers_section'),
    
    # The new Earnings section
    path('earnings/', views.earning_dashboard_view, name='lawyer_earnings'),
    # Add this to your urlpatterns inside lawyers/urls.py
    path('orders/', views.case_order_view, name='lawyer_case_orders'),
    # Add this to your urlpatterns inside lawyers/urls.py
    path('status/', views.case_status_view, name='lawyer_case_status'),
    # Add this to your urlpatterns inside lawyers/urls.py
    path('settings/', views.account_settings_view, name='lawyer_settings'),
    # Add this to your urlpatterns inside lawyers/urls.py
    path('billing/', views.billing_payment_view, name='lawyer_billing'),
    # Add this to your urlpatterns inside lawyers/urls.py
    path('support/', views.support_lawyer_view, name='lawyer_support'),
    # Add this to your urlpatterns inside lawyers/urls.py
    path('report-client/', views.report_client_view, name='lawyer_report_client'),

]
