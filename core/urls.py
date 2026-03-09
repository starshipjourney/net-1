from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('net1-control/', admin.site.urls),
    path('', include('interface.urls')),
    path('data-master/', include('data_master.urls')),
    path('system-logger/',    include('system_logger.urls')),
]