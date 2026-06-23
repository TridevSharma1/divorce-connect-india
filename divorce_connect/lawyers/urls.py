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

]
