import os
import json
import subprocess
import threading
import time
from pathlib import Path
from django.shortcuts import render, redirect
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import psutil
import requests

# ============================================================
#  ADMIN GUARD
# ============================================================
def admin_required(view_fn):
    """Decorator: only superusers/staff can access."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'error': 'Admin access required'}, status=403)
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


# ============================================================
#  PATHS
# ============================================================
MAIN_DIR  = Path(settings.BASE_DIR)
BASE_DIR  = MAIN_DIR.parent
DUMPS_DIR = BASE_DIR / 'data' / 'dumps'

# read from llm module — same source as the prompt screen uses
import data_master.llm as _llm_module
OLLAMA_HOST  = _llm_module.OLLAMA_HOST
OLLAMA_MODEL = _llm_module.OLLAMA_MODEL

# ============================================================
#  SOURCE DEFINITIONS
# ============================================================
SYNC_SOURCES = {
    'wikipedia' : {'label': 'Wikipedia',  'icon': '📄', 'parser': 'data_master/parser.py',           'dump_key': 'wiki'},
    'wikibooks' : {'label': 'Wikibooks',  'icon': '📚', 'parser': 'data_master/wikibooks_parser.py', 'dump_key': 'wikibooks'},
    'wikivoyage': {'label': 'Wikivoyage', 'icon': '🗺️', 'parser': 'data_master/wikivoyage_parser.py','dump_key': 'wikivoyage'},
    'gutenberg' : {'label': 'Gutenberg',  'icon': '📖', 'parser': 'data_master/gutenberg_parser.py', 'dump_key': 'gutenberg'},
    'ifixit'    : {'label': 'iFixit',     'icon': '🔧', 'parser': 'data_master/ifixit_parser.py',    'dump_key': 'ifixit'},
    'arxiv'     : {'label': 'arXiv',      'icon': '🔬', 'parser': 'data_master/arxiv_parser.py',     'dump_key': 'arxiv'},
}

# ============================================================
#  SYSTEM STATUS  (used by dashboard polling too)
# ============================================================
_START_TIME = time.time()

@require_GET
def status_view(request):
    """System status — CPU, RAM, disk, uptime. Public (used by dashboard)."""
    try:
        cpu  = psutil.cpu_percent(interval=0.1)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage(str(BASE_DIR))

        elapsed = int(time.time() - _START_TIME)
        h, m    = divmod(elapsed // 60, 60)
        uptime  = f'{h}h {m}m'

        return JsonResponse({
            'net1_online': True,
            'uptime'     : uptime,
            'cpu'        : {'percent': cpu},
            'ram'        : {
                'percent' : ram.percent,
                'used_gb' : round(ram.used / 1e9, 1),
                'total_gb': round(ram.total / 1e9, 1),
            },
            'disk'       : {
                'percent' : disk.percent,
                'used_gb' : round(disk.used / 1e9, 1),
                'total_gb': round(disk.total / 1e9, 1),
            },
        })
    except Exception as e:
        return JsonResponse({'net1_online': False, 'error': str(e)})


# ============================================================
#  SYSTEM PAGE
# ============================================================
@login_required(login_url='login')
def system_view(request):
    """Main system admin page — admin only."""
    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, 'system_logger/access_denied.html', status=403)

    # document counts per source
    from data_master.models import Document, Source
    source_counts = {}
    source_dates  = {}
    for key in SYNC_SOURCES:
        source_counts[key] = Document.objects.filter(
            source_type=key, is_active=True
        ).count()
        last = Source.objects.filter(
            source_type=key
        ).order_by('-loaded_at').first()
        source_dates[key] = last.loaded_at.strftime('%Y-%m-%d %H:%M') if last else 'Never'

    import json
    source_data = {}
    for key in SYNC_SOURCES:
        source_data[key] = {
            'count': source_counts.get(key, 0),
            'date' : source_dates.get(key, 'Never'),
        }
    source_data_json = json.dumps(source_data)

    return render(request, 'system_logger/system.html', {
        'sync_sources'    : SYNC_SOURCES,
        'source_counts'   : source_counts,
        'source_dates'    : source_dates,
        'source_data_json': source_data_json,
        'ollama_host'     : OLLAMA_HOST,
        'active_model'    : OLLAMA_MODEL,
    })


# ============================================================
#  DATA SYNC
# ============================================================
# in-memory sync job tracker
_sync_jobs = {}   # job_id → {'status', 'log', 'source', 'phase'}
_sync_lock = threading.Lock()


@require_POST
@login_required(login_url='login')
def sync_start(request):
    """Start a data sync job for selected sources."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)

    try:
        data    = json.loads(request.body)
        sources = data.get('sources', [])
        mode    = data.get('mode', 'sample')   # 'sample' | 'full'

        if not sources:
            return JsonResponse({'error': 'No sources selected'}, status=400)

        # validate sources
        invalid = [s for s in sources if s not in SYNC_SOURCES]
        if invalid:
            return JsonResponse({'error': f'Unknown sources: {invalid}'}, status=400)

        import uuid
        job_id = str(uuid.uuid4())[:8]

        with _sync_lock:
            _sync_jobs[job_id] = {
                'status' : 'running',
                'log'    : [],
                'sources': sources,
                'mode'   : mode,
                'started': time.time(),
            }

        # run in background thread
        thread = threading.Thread(
            target=_run_sync,
            args=(job_id, sources, mode, str(MAIN_DIR)),
            daemon=True,
        )
        thread.start()

        return JsonResponse({'job_id': job_id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _run_sync(job_id, sources, mode, main_dir):
    """Background thread — runs download + parser for each source."""
    import sys

    def log(msg):
        with _sync_lock:
            _sync_jobs[job_id]['log'].append(msg)

    try:
        python = sys.executable

        for source in sources:
            meta = SYNC_SOURCES[source]
            dump_key = meta['dump_key']

            log(f'[{source}] Starting {"sample" if mode == "sample" else "full"} sync...')

            # ── Phase 1: Download ──
            log(f'[{source}] Downloading data...')
            with _sync_lock:
                _sync_jobs[job_id]['phase'] = f'{source}:download'

            dl_args = [python, 'download_data.py', '--sources', dump_key]
            if mode == 'sample':
                dl_args.append('--sample')

            try:
                result = subprocess.run(
                    dl_args,
                    cwd=main_dir,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )
                for line in result.stdout.splitlines()[-20:]:  # last 20 lines
                    if line.strip():
                        log(f'[{source}] {line}')
                if result.returncode != 0:
                    log(f'[{source}] ⚠ Download warnings: {result.stderr[:200]}')
            except subprocess.TimeoutExpired:
                log(f'[{source}] ❌ Download timed out')
                continue

            # ── Phase 2: Parse ──
            log(f'[{source}] Parsing into database...')
            with _sync_lock:
                _sync_jobs[job_id]['phase'] = f'{source}:parse'

            parser = meta['parser']
            try:
                result = subprocess.run(
                    [python, parser],
                    cwd=main_dir,
                    capture_output=True,
                    text=True,
                    timeout=7200,
                )
                for line in result.stdout.splitlines()[-20:]:
                    if line.strip():
                        log(f'[{source}] {line}')
                if result.returncode != 0:
                    log(f'[{source}] ❌ Parser error: {result.stderr[:200]}')
                else:
                    log(f'[{source}] ✅ Sync complete')
            except subprocess.TimeoutExpired:
                log(f'[{source}] ❌ Parser timed out')

        with _sync_lock:
            _sync_jobs[job_id]['status'] = 'done'
            _sync_jobs[job_id]['phase']  = 'complete'

        log('✅ All selected sources synced successfully')

    except Exception as e:
        with _sync_lock:
            _sync_jobs[job_id]['status'] = 'error'
        log(f'❌ Fatal error: {e}')


@require_GET
@login_required(login_url='login')
def sync_status(request, job_id):
    """Poll sync job status and log."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)

    with _sync_lock:
        job = _sync_jobs.get(job_id)

    if not job:
        return JsonResponse({'error': 'Job not found'}, status=404)

    return JsonResponse({
        'status' : job['status'],
        'log'    : job['log'],
        'phase'  : job.get('phase', ''),
    })


# ============================================================
#  LLM MANAGEMENT  (Ollama API)
# ============================================================
def _ollama(method, path, **kwargs):
    """Helper to call Ollama API."""
    url = f'{OLLAMA_HOST}/api/{path}'
    fn  = getattr(requests, method)
    return fn(url, timeout=30, **kwargs)


@require_GET
@login_required(login_url='login')
def llm_list(request):
    """List all locally available Ollama models."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)
    try:
        resp   = _ollama('get', 'tags')
        models = resp.json().get('models', [])
        result = []
        for m in models:
            size_gb = round(m.get('size', 0) / 1e9, 2)
            result.append({
                'name'      : m['name'],
                'size_gb'   : size_gb,
                'modified'  : m.get('modified_at', '')[:10],
                'is_active' : m['name'] == OLLAMA_MODEL,
            })
        return JsonResponse({'models': result, 'active': OLLAMA_MODEL})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required(login_url='login')
def llm_set_active(request):
    """Set the active LLM model used by the prompt screen."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)
    try:
        global OLLAMA_MODEL
        data  = json.loads(request.body)
        model = data.get('model', '').strip()
        if not model:
            return JsonResponse({'error': 'Model name required'}, status=400)

        OLLAMA_MODEL = model

        # also update the llm module so prompt screen uses new model immediately
        _llm_module.OLLAMA_MODEL = model
        _llm_module.client       = _llm_module.ollama.Client(host=_llm_module.OLLAMA_HOST)

        return JsonResponse({'ok': True, 'active': model})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required(login_url='login')
def llm_delete(request):
    """Delete a local Ollama model."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)
    try:
        data  = json.loads(request.body)
        model = data.get('model', '').strip()
        if not model:
            return JsonResponse({'error': 'Model name required'}, status=400)
        if model == OLLAMA_MODEL:
            return JsonResponse({'error': 'Cannot delete the active model'}, status=400)

        resp = _ollama('delete', 'delete', json={'name': model})
        if resp.status_code in (200, 204):
            return JsonResponse({'ok': True})
        return JsonResponse({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── Pull (download) with streaming progress ──

_pull_jobs = {}   # model_name → {'status', 'progress', 'log'}
_pull_lock = threading.Lock()


@require_POST
@login_required(login_url='login')
def llm_pull(request):
    """Start downloading a new Ollama model."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)
    try:
        data  = json.loads(request.body)
        model = data.get('model', '').strip()
        if not model:
            return JsonResponse({'error': 'Model name required'}, status=400)

        with _pull_lock:
            _pull_jobs[model] = {'status': 'pulling', 'progress': 0, 'log': []}

        thread = threading.Thread(
            target=_run_pull,
            args=(model,),
            daemon=True,
        )
        thread.start()

        return JsonResponse({'ok': True, 'model': model})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _run_pull(model):
    """Pull model from Ollama with progress tracking."""
    def log(msg):
        with _pull_lock:
            _pull_jobs[model]['log'].append(msg)

    try:
        resp = requests.post(
            f'{OLLAMA_HOST}/api/pull',
            json={'name': model, 'stream': True},
            stream=True,
            timeout=7200,
        )
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
                status = data.get('status', '')

                if 'total' in data and 'completed' in data:
                    pct = int(data['completed'] / data['total'] * 100)
                    with _pull_lock:
                        _pull_jobs[model]['progress'] = pct
                    log(f'{status} — {pct}%')
                elif status:
                    log(status)

                if status == 'success':
                    with _pull_lock:
                        _pull_jobs[model]['status']   = 'done'
                        _pull_jobs[model]['progress'] = 100
                    log('✅ Download complete')
                    return

            except json.JSONDecodeError:
                continue

        with _pull_lock:
            _pull_jobs[model]['status'] = 'done'
            _pull_jobs[model]['progress'] = 100

    except Exception as e:
        with _pull_lock:
            _pull_jobs[model]['status'] = 'error'
        log(f'❌ Error: {e}')


@require_GET
@login_required(login_url='login')
def llm_pull_status(request, model):
    """Poll pull progress for a model."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)

    with _pull_lock:
        job = _pull_jobs.get(model)

    if not job:
        return JsonResponse({'error': 'No pull job found'}, status=404)

    return JsonResponse({
        'status'  : job['status'],
        'progress': job['progress'],
        'log'     : job['log'][-5:],  # last 5 lines
    })