from django.db import models


class SystemSnapshot(models.Model):
    """
    Periodic system health snapshot.
    Stored every 30 seconds, retained for 5 days.
    """
    timestamp     = models.DateTimeField(auto_now_add=True, db_index=True)

    # network
    net1_online   = models.BooleanField(default=False)

    # resources
    cpu_percent   = models.FloatField(default=0)
    ram_percent   = models.FloatField(default=0)
    ram_used_gb   = models.FloatField(default=0)
    ram_total_gb  = models.FloatField(default=0)
    disk_percent  = models.FloatField(default=0)
    disk_used_gb  = models.FloatField(default=0)
    disk_total_gb = models.FloatField(default=0)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Snapshot {self.timestamp:%Y-%m-%d %H:%M:%S}"