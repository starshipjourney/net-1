from django.db import models
from django.contrib.auth.models import User

# ============================================================
#  SYSTEM LOG  — review system recource use
# ============================================================
class SystemSnapshot(models.Model):
    """Periodic system health snapshot — collected every 60 seconds."""
    timestamp     = models.DateTimeField(auto_now_add=True, db_index=True)
    net1_online   = models.BooleanField(default=True)
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
    
# ============================================================
#  ACTIVITY LOG  — user page visits and actions
# ============================================================
class ActivityLog(models.Model):

    ACTION_CHOICES = [
        ('page_view',  'Page View'),
        ('prompt',     'LLM Prompt'),
        ('search',     'Search'),
        ('download',   'Download'),
        ('sync',       'Data Sync'),
        ('llm_manage', 'LLM Management'),
        ('login',      'Login'),
        ('logout',     'Logout'),
        ('note_create',  'Note Created'),
        ('note_edit',    'Note Edited'),
        ('note_comment', 'Note Comment'),
        ('other',        'Other'),
    ]

    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)
    user        = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activity_logs'
    )
    username    = models.CharField(max_length=150, blank=True)
    action      = models.CharField(max_length=20, choices=ACTION_CHOICES, default='page_view')
    path        = models.CharField(max_length=500)
    detail      = models.CharField(max_length=500, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes  = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M} [{self.username}] {self.action} {self.path}'