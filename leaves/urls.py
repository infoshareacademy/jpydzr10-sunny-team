from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('my-vacations/', views.vacation_list, name='vacation_list'),
]
