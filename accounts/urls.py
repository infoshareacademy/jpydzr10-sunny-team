from django.urls import path
from . import views
from .views import ProfileView

urlpatterns = [
    path('users/deactivate/<int:pk>', views.deactivate_user, name='deactivate_user'),
    path('user_list/', views.user_list, name='user_list'),
    path('switch-role/', views.switch_role, name='switch_role'),
    path("add-user/", views.add_user, name="add_user"),
    path("user/edit/<int:user_id>/", views.edit_user, name="edit_user"),
    path("change-password/", views.change_own_password, name="change_own_password"),
    path('profile/<int:user_id>/', ProfileView.as_view(), name='profile'),
    path('profile/assign/<int:user_id>/', views.assign_worker_profile, name='assign_worker_profile'),
    path('profile/edit/<int:user_id>/', views.edit_worker_profile, name='edit_worker_profile'),
]
