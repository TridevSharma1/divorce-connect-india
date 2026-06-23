from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.edit_profile_admin_view, name='edit_profile_admin'),
]
