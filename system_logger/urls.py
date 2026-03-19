from django.urls import path
from system_logger import views

urlpatterns = [
    # ── System page ────────────────────────────────────────────
    path('',               views.system_view,    name='system'),
    path('status/',        views.status_view,    name='system_status'),

    # ── Data sync ──────────────────────────────────────────────
    path('sync/start/',             views.sync_start,  name='sync_start'),
    path('sync/status/<str:job_id>/', views.sync_status, name='sync_status'),

    # ── LLM management ─────────────────────────────────────────
    path('llm/list/',                    views.llm_list,        name='llm_list'),
    path('llm/set-active/',              views.llm_set_active,  name='llm_set_active'),
    path('llm/delete/',                  views.llm_delete,      name='llm_delete'),
    path('llm/pull/',                    views.llm_pull,        name='llm_pull'),
    path('llm/pull-status/<str:model>/', views.llm_pull_status, name='llm_pull_status'),
]