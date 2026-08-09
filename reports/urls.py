from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_index, name='reports_index'),
    path('users-per-role/', views.users_per_role_report, name='users_per_role_report'),
    path('users-per-role/export/csv', views.export_users_per_role_csv, name='export_users_per_role_csv'),
    path('users-per-role/export/pdf/', views.export_users_per_role_pdf, name='export_users_per_role_pdf'),
    path('leave-usage/', views.leave_usage_report, name='leave_usage_report'),
    path('leave-usage/export/csv', views.export_leave_usage_csv, name='export_leave_usage_csv'),
    path('leave-usage/export/pdf/', views.export_leave_usage_pdf, name='export_leave_usage_pdf'),
    path('team/', views.team_report, name='team_report'),
    path('team/export/csv', views.export_team_report_csv, name='export_team_report_csv'),
    path('team/export/pdf/', views.export_team_report_pdf, name='export_team_report_pdf'),
    path('logs/activity/export/csv/', views.export_activity_log_csv, name='export_activity_log_csv'),
    path('logs/activity/export/pdf/', views.export_activity_log_pdf, name='export_activity_log_pdf'),
    path('logs/auth/export/csv/', views.export_auth_log_csv, name='export_auth_log_csv'),
    path('logs/auth/export/pdf/', views.export_auth_log_pdf, name='export_auth_log_pdf'),
    path('leave-requests/', views.leave_requests_report_list, name='leave_requests_report_list'),
    path('leave-requests/export/csv/', views.export_leave_requests_csv, name='export_leave_requests_csv'),
    path('leave-requests/export/pdf/', views.export_leave_requests_pdf, name='export_leave_requests_pdf'),
    path('team/export/', views.export_team_report_csv, name='export_team_report_csv'),
    path('charts/leave-over-time/', views.chart_leave_over_time, name='chart_leave_over_time'),
    path('charts/team-workload/', views.chart_team_workload, name='chart_team_workload'),  
]