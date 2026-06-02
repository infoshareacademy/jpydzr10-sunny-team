from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('my-vacations/', views.my_vacations, name='my_vacations'),
    path('all-requests/', views.all_requests_list, name='all_requests_list'),
    path('new-request/', views.LeaveRequestView.as_view(), name='new_request'),
    path('approve/<int:request_id>/', views.approve_request, name='approve_request'),
    path('reject/<int:request_id>/', views.reject_request, name='reject_request'),
    path('logs/', views.log_history, name='log_history'),
    path('team-balance/', views.team_leave_balance, name='team_leave_balance'),
    path('export-csv/', views.export_requests_csv, name='export_requests_csv'),
    path('team-calendar/', views.team_calendar, name='team_calendar'),
    path('edit-request/<int:pk>/', views.LeaveRequestUpdateView.as_view(), name='leave_request_edit'),
    path('cancel-request/<int:pk>/', views.CancelLeaveView.as_view(), name='leave_request_cancel'),
    path("add-user/", views.add_user, name="add_user"),
    path("reset-password/", views.reset_password, name="reset_password"),


]
