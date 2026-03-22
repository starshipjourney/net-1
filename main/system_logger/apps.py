from django.apps import AppConfig
 
 
class SystemLoggerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'system_logger'
 
    def ready(self):
        """Start background metric collector when Django boots."""
        import os
 
        # In dev (runserver), Django forks a reloader — RUN_MAIN is 'true'
        # in the child and not set in the parent. We skip the parent to avoid
        # starting two collectors.
        # In production (Gunicorn), RUN_MAIN is never set so we always start.
        if os.environ.get('RUN_MAIN') == 'false':
            return
 
        from .collector import start_collector
        start_collector()
 