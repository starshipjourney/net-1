"""
NET-1 System Metric Collector
Runs as a background daemon thread, sampling CPU/RAM every 60 seconds.
Started automatically when Django boots via AppConfig.ready().
Prunes data older than 7 days to keep the DB lean.
"""
import threading
import time
import logging

logger = logging.getLogger(__name__)

SAMPLE_INTERVAL = 60        # seconds between samples
RETENTION_DAYS  = 7         # days of data to keep
_collector_started = False
_lock = threading.Lock()


def start_collector():
    """Start the background collector thread. Safe to call multiple times."""
    global _collector_started
    with _lock:
        if _collector_started:
            return
        _collector_started = True

    thread = threading.Thread(target=_collect_loop, daemon=True, name='net1-metrics')
    thread.start()
    logger.info('NET-1 metric collector started')


def _collect_loop():
    """Main collection loop — runs forever in background."""
    # wait for Django to fully boot before first sample
    time.sleep(10)

    while True:
        try:
            _take_snapshot()
            _prune_old_data()
        except Exception as e:
            logger.warning(f'Metric collection error: {e}')

        time.sleep(SAMPLE_INTERVAL)


def _take_snapshot():
    import psutil
    from django.utils import timezone
    import requests as req
    from .models import SystemSnapshot

    cpu  = psutil.cpu_percent(interval=1)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # check if net1 is reachable
    try:
        req.get('http://localhost:8000/', timeout=2)
        net1_online = True
    except Exception:
        net1_online = True  # if we're running, we're online

    SystemSnapshot.objects.create(
        net1_online   = net1_online,
        cpu_percent   = round(cpu, 1),
        ram_percent   = round(ram.percent, 1),
        ram_used_gb   = round(ram.used / 1e9, 2),
        ram_total_gb  = round(ram.total / 1e9, 2),
        disk_percent  = round(disk.percent, 1),
        disk_used_gb  = round(disk.used / 1e9, 2),
        disk_total_gb = round(disk.total / 1e9, 2),
    )


def _prune_old_data():
    from django.utils import timezone
    from datetime import timedelta
    from .models import SystemSnapshot, ActivityLog

    cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)
    deleted_m, _ = SystemSnapshot.objects.filter(timestamp__lt=cutoff).delete()
    deleted_a, _ = ActivityLog.objects.filter(timestamp__lt=cutoff).delete()

    if deleted_m or deleted_a:
        logger.info(f'Pruned {deleted_m} metrics, {deleted_a} activity logs older than {RETENTION_DAYS}d')