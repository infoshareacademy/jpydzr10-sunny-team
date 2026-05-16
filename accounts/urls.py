from django.urls import path
from . import views

urlpatterns = [
    path('users/<int:pk>/deactivate/', views.deactivate_user, name='deactivate_user'),
]
