from django.urls import path
from . import views

urlpatterns = [
    # This keeps your landing page at http://127.0.0.1:8000/
    path('', views.landing_page_view, name='landing_page'), 
]