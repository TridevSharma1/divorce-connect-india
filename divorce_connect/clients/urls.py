from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page_view, name='landing_page'),
    path('dashboard/', views.client_dashboard_view, name='client_dashboard'),
    path('profile/', views.client_profile_view, name='client_profile'),
]