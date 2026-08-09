from django.urls import path
from . import views

urlpatterns = [

    path('activity/', views.activity_log_history, name='activity_log'),
    path('auth/', views.auth_log_history, name='auth_log'),
    ]
    path('history/', views.log_history, name='log_history'),
    path('history/<int:pk>/', views.log_detail, name='log_detail'),
]
