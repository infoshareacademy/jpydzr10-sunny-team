from django.urls import path
from . import views

urlpatterns = [
    path('history/', views.log_history, name='log_history'),
    path('history/<int:pk>/', views.log_detail, name='log_detail'),
]