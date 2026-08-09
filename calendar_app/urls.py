from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('leaves/', include('leaves.urls')),
    path('admin_panel/',include('admin_panel.urls')),
    path('logs/',include('logs.urls')),
    path('login/',include('login.urls')),
    path('reports/', include('reports.urls')),
    path('', include('core.urls')),
    path('login/', include('login.urls')),
    path('team/', include('team.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('reset-password/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html'
         ),
         name='password_reset'),
    path('reset-password/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset-password/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('reset-password/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    ]
