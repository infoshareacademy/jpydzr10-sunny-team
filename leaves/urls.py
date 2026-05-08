from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('my-vacations/', views.my_vacations, name='my_vacations'),
    path('all-requests/', views.all_requests_list, name='all_requests_list'),
]
