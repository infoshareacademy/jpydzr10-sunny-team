from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_index, name='reports_index'),
    path('users-per-role/', views.users_per_role_report, name='users_per_role_report'),
]