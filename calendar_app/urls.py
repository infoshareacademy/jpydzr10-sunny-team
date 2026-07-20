from django.contrib import admin
from django.urls import path,include


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
]