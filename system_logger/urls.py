from django.urls import path
from system_logger.status import system_status_view

urlpatterns = [
    path('status/', system_status_view, name='system_status'),
]