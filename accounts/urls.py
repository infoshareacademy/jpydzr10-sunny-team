from django.urls import path
from . import views

urlpatterns = [
    path('users/deactivate/<int:pk>', views.deactivate_user, name='deactivate_user'),
]
