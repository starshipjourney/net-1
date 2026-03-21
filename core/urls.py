from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import logout as auth_logout
from django.views.decorators.http import require_POST
from django.shortcuts import redirect

@require_POST
def logout_view(request):
    try:
        request.session.delete()
    except Exception:
        pass
    auth_logout(request)
    return redirect('login')

urlpatterns = [
    path('net1-control/', admin.site.urls),
    path('', include('interface.urls')),
    path('data-master/', include('data_master.urls')),
    path('system-logger/', include('system_logger.urls')),
    path('notes/', include('notes.urls')),
    path('logout/', logout_view, name='logout'),
] + static(settings.STATIC_URL,  document_root=settings.STATIC_ROOT) \
  + static(settings.MEDIA_URL,   document_root=settings.MEDIA_ROOT)