from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('my-vacations/', views.vacation_list, name='vacation_list'),
    path('all-requests/', views.all_requests_list, name='all_requests_list'),
]
