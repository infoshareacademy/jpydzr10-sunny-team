from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('logout/', views.logout_view, name='logout'),
    path('', views.login_view, name='login'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path(
        'first_password_change/',
        views.FirstPasswordChangeView.as_view(),
        name='first_password_change'
    ),
    path(
        'first_password_change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='first_password_change_done.html'
        ),
        name='first_password_change_done'
    ),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<uuid:token>/', views.reset_password_confirm, name='reset_password_confirm'),
]