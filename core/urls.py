from django.urls import path
from core.views import MainPageView

urlpatterns = [
    path('', MainPageView.as_view(), name='home'),
]