from django.apps import AppConfig


class SystemLoggerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'system_logger'

    def ready(self):
        """Start background metric collector when Django boots."""
        import os
        # only start in the main process — not in reloader child processes
        if os.environ.get('RUN_MAIN') != 'true':
            return
        from .collector import start_collector
        start_collector()