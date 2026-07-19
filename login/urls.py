from django.urls import path
from . import views
urlpatterns = [
    path('logout/', views.logout_view, name='logout'),
    path('', views.login_view, name='login'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa')
]