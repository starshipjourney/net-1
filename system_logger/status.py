import time
import psutil
import subprocess
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from system_logger.models import SystemSnapshot


RETENTION_DAYS = 5


def check_net1_network():
    """Check if the net1-network podman network is active."""
    try:
        result = subprocess.run(
            ['podman', 'network', 'inspect', 'net1-network'],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


def collect_stats():
    net1_online  = check_net1_network()

    cpu_percent  = psutil.cpu_percent(interval=0)

    ram          = psutil.virtual_memory()
    ram_used_gb  = round(ram.used  / (1024 ** 3), 1)
    ram_total_gb = round(ram.total / (1024 ** 3), 1)
    ram_percent  = ram.percent

    try:
        disk          = psutil.disk_usage('/media/starship/m3_ssd')
        disk_used_gb  = round(disk.used  / (1024 ** 3), 1)
        disk_total_gb = round(disk.total / (1024 ** 3), 1)
        disk_percent  = disk.percent
    except Exception:
        disk_used_gb = disk_total_gb = disk_percent = 0

    uptime_seconds = int(time.time() - psutil.boot_time())
    days    = uptime_seconds // 86400
    hours   = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600)  // 60

    return {
        'net1_online'  : net1_online,
        'cpu_percent'  : cpu_percent,
        'ram_used_gb'  : ram_used_gb,
        'ram_total_gb' : ram_total_gb,
        'ram_percent'  : ram_percent,
        'disk_used_gb' : disk_used_gb,
        'disk_total_gb': disk_total_gb,
        'disk_percent' : disk_percent,
        'uptime'       : f"{days}d {hours}h {minutes}m",
    }


def save_snapshot(stats):
    SystemSnapshot.objects.create(
        net1_online   = stats['net1_online'],
        cpu_percent   = stats['cpu_percent'],
        ram_percent   = stats['ram_percent'],
        ram_used_gb   = stats['ram_used_gb'],
        ram_total_gb  = stats['ram_total_gb'],
        disk_percent  = stats['disk_percent'],
        disk_used_gb  = stats['disk_used_gb'],
        disk_total_gb = stats['disk_total_gb'],
    )

    cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)
    deleted, _ = SystemSnapshot.objects.filter(timestamp__lt=cutoff).delete()
    if deleted:
        print(f"🧹 Cleaned {deleted} old snapshots")


@login_required(login_url='login')
def system_status_view(request):
    stats = collect_stats()
    save_snapshot(stats)

    return JsonResponse({
        'net1_online': stats['net1_online'],
        'cpu'  : { 'percent' : stats['cpu_percent'] },
        'ram'  : {
            'used_gb' : stats['ram_used_gb'],
            'total_gb': stats['ram_total_gb'],
            'percent' : stats['ram_percent'],
        },
        'disk' : {
            'used_gb' : stats['disk_used_gb'],
            'total_gb': stats['disk_total_gb'],
            'percent' : stats['disk_percent'],
        },
        'uptime': stats['uptime'],
    })