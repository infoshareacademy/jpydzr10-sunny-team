from django.urls import path
from . import views

urlpatterns = [
    path('users/deactivate/<int:pk>', views.deactivate_user, name='deactivate_user'),
    path('user_list', views.user_list, name='user_list'),
    path('switch-role/', views.switch_role, name='switch_role'),
    path("add-user/", views.add_user, name="add_user"),
    path("reset-password/", views.reset_password, name="reset_password"),
]
