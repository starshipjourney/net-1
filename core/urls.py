from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('net1-control/', admin.site.urls),
    path('', include('interface.urls')),
    path('data-master/', include('data_master.urls')),
    path('system-logger/',    include('system_logger.urls')),
    path('notes/', include('notes.urls')),
]  + static(settings.STATIC_URL,  document_root=settings.STATIC_ROOT) \
  + static(settings.MEDIA_URL,   document_root=settings.MEDIA_ROOT)