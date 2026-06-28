from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('verify-register-otp/', views.verify_register_otp_view, name='verify_register_otp'),
    path('delete-account/', views.request_delete_account_view, name='request_delete_account'),
    path('confirm-delete/<str:token>/', views.confirm_delete_account_view, name='confirm_delete_account'),
]