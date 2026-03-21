"""
NET-1 Activity Logging Middleware
Logs every authenticated user request to ActivityLog.
Skips static files, favicon, and polling endpoints.
"""
import re
from .models import ActivityLog

# paths to skip — static files, polling, health checks
_SKIP_PATTERNS = re.compile(
    r'^(/static/|/media/|/favicon|'
    r'/system-logger/status/|'
    r'/system-logger/sync/status/|'
    r'/system-logger/llm/pull-status/|'
    r'/data-master/prompt/history/|'
    r'/data-master/catalogue/thumb/|'
    r'/data-master/catalogue/search/|'
    r'/system-logger/llm/list/'
    r')'
)

# map URL patterns to action types
_ACTION_MAP = [
    (re.compile(r'^/data-master/prompt/$'),           'prompt'),
    (re.compile(r'^/data-master/catalogue/search/'),  'search'),
    (re.compile(r'^/data-master/library/search/'),    'search'),
    (re.compile(r'^/data-master/catalogue/pdf/'),     'download'),
    (re.compile(r'^/system-logger/sync/start/'),      'sync'),
    (re.compile(r'^/system-logger/llm/'),             'llm_manage'),
    (re.compile(r'^/notes/new/'),                     'note_create'),      # POST only
    (re.compile(r'^/notes/.+/comment/'),              'note_comment'),     # POST only
    (re.compile(r'^/notes/.+/edit/'),                 'note_edit'),        # POST only
    (re.compile(r'^/login/'),                         'login'),
    (re.compile(r'^/logout/'),                        'logout'),
]


_POST_ONLY_ACTIONS = {'note_create', 'note_comment', 'note_edit', 'sync', 'prompt', 'llm_manage'}

def _get_action(path, method):
    for pattern, action in _ACTION_MAP:
        if pattern.match(path):
            # only log POST for write actions — skip GET (page loads)
            if action in _POST_ONLY_ACTIONS and method != 'POST':
                return None
            return action
    return 'page_view'


def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # only log authenticated users
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return response

        path = request.path
        if _SKIP_PATTERNS.match(path):
            return response

        # only log GET (page views) and POST (actions)
        if request.method not in ('GET', 'POST'):
            return response

        # skip non-200/201 responses for page views to reduce noise
        if _get_action(path, request.method) == 'page_view' and response.status_code not in (200, 201):
            return response

        action = _get_action(path, request.method)
        if action is None:
            return response

        try:
            ActivityLog.objects.create(
                user        = request.user,
                username    = request.user.username,
                action      = action,
                path        = path[:500],
                ip_address  = _get_ip(request),
                session_key = request.session.session_key or '',
            )
        except Exception:
            pass  # never let logging break the request

        return response