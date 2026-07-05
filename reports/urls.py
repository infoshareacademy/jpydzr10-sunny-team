from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_index, name='reports_index'),
    path('users-per-role/', views.users_per_role_report, name='users_per_role_report'),
    path('leave-usage/', views.leave_usage_report, name='leave_usage_report'),
    path('leave-usage/export/', views.export_leave_usage_csv, name='export_leave_usage_csv'),
    path('team/', views.team_report, name='team_report'),
    path('team/export/', views.export_team_report_csv, name='export_team_report_csv'),
]