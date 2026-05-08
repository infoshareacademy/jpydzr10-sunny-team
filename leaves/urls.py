from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('my-vacations/', views.vacation_list, name='vacation_list'),
    path('all-requests/', views.all_requests_list, name='all_requests_list'),
    path('new-request/', views.new_request, name='new_request'),
    path('calculate-days/', views.calculate_days_api, name='calculate_days_api'),

]
