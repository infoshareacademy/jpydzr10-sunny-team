from django.urls import path
from . import views

urlpatterns = [
    path('users/deactivate/<int:pk>', views.deactivate_user, name='deactivate_user'),
    path('user_list', views.user_list, name='user_list'),
    path('switch-role/', views.switch_role, name='switch_role'),
    path('profile/', views.profile, name='profile'),
]
