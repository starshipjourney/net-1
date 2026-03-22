#!/usr/bin/env python
"""
NET-1 Production Cleanup Script
================================
Run this ONCE before going live to wipe all dev/test data.
Keeps your document content, PDF library and user accounts intact.

Usage:
    cd /media/starship/m3_ssd/net-1/main
    python cleanup_for_production.py

Or inside the container:
    podman-compose exec django python cleanup_for_production.py
"""

import os
import sys
import django

# Bootstrap Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.sessions.models import Session
from django.utils import timezone

def confirm(msg):
    ans = input(f'\n{msg} [y/N]: ').strip().lower()
    if ans != 'y':
        print('  Skipped.')
        return False
    return True

print('\n' + '='*60)
print('  NET-1 PRODUCTION CLEANUP')
print('='*60)
print('\nThis script removes dev/test data before going live.')
print('Document content, PDFs, and user accounts are NOT touched.\n')

# ── 1. Activity Log ──────────────────────────────────────────
if confirm('Clear all ActivityLog entries (dev browsing history)?'):
    from system_logger.models import ActivityLog
    count = ActivityLog.objects.count()
    ActivityLog.objects.all().delete()
    print(f'  ✅ Deleted {count} activity log entries.')

# ── 2. System Snapshots ──────────────────────────────────────
if confirm('Clear all SystemSnapshot entries (dev metrics)?'):
    from system_logger.models import SystemSnapshot
    count = SystemSnapshot.objects.count()
    SystemSnapshot.objects.all().delete()
    print(f'  ✅ Deleted {count} system snapshots.')

# ── 3. Sessions ──────────────────────────────────────────────
if confirm('Clear all sessions (will log everyone out)?'):
    count = Session.objects.count()
    Session.objects.all().delete()
    print(f'  ✅ Deleted {count} sessions.')

# ── 4. Valkey chat history ───────────────────────────────────
if confirm('Clear all Valkey chat history for all users?'):
    try:
        from django.core.cache import cache
        # NET-1 chat keys follow pattern net1:chat:<username>
        from django_valkey import get_redis_connection
        conn = get_redis_connection('default')
        keys = conn.keys('*net1*chat*')
        if keys:
            conn.delete(*keys)
            print(f'  ✅ Deleted {len(keys)} Valkey chat history keys.')
        else:
            print('  ✅ No Valkey chat keys found.')
    except Exception as e:
        print(f'  ⚠ Could not clear Valkey: {e}')
        print('    You can clear manually: podman exec net1-valkey valkey-cli FLUSHDB')

# ── 5. Dev user accounts ─────────────────────────────────────
if confirm('List and optionally delete non-superuser accounts?'):
    from django.contrib.auth.models import User
    users = User.objects.filter(is_superuser=False)
    if not users.exists():
        print('  No non-superuser accounts found.')
    else:
        print('\n  Non-superuser accounts:')
        for u in users:
            print(f'    [{u.id}] {u.username} (staff={u.is_staff}, active={u.is_active})')
        ids = input('\n  Enter IDs to delete (comma-separated) or ENTER to skip: ').strip()
        if ids:
            id_list = [i.strip() for i in ids.split(',') if i.strip().isdigit()]
            deleted = User.objects.filter(pk__in=id_list).delete()
            print(f'  ✅ Deleted {deleted[0]} user(s).')

# ── 6. Notes ─────────────────────────────────────────────────
if confirm('Clear all notes (dev test notes)?'):
    try:
        from notes.models import Note
        count = Note.objects.count()
        Note.objects.all().delete()
        print(f'  ✅ Deleted {count} notes.')
    except Exception as e:
        print(f'  ⚠ {e}')

print('\n' + '='*60)
print('  CLEANUP COMPLETE')
print('='*60)
print('\nNext steps:')
print('  1. Create your production superuser:')
print('     python manage.py createsuperuser')
print('  2. Pull your LLM model if not already done:')
print('     podman exec net1-ollama ollama pull qwen3:8b')
print('  3. Run a data sync from the SYSTEM page')
print('  4. You\'re live.\n')
