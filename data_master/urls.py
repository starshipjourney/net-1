from django.urls import path
from data_master import views

urlpatterns = [
    # ── Catalogue ──────────────────────────────────────────────
    path('catalogue/',                        views.catalogue_view,    name='catalogue'),
    path('catalogue/search/',                 views.catalogue_search,  name='catalogue_search'),
    path('catalogue/pdf/<path:filepath>',     views.serve_pdf,         name='serve_pdf'),
    path('catalogue/thumb/<str:filename>',    views.serve_thumb,       name='serve_thumb'),
    path('catalogue/gen-thumb/<path:filepath>', views.generate_thumb,  name='generate_thumb'),
 
    # ── PDF Library ────────────────────────────────────────────
    path('library/',                          views.pdf_library_view,  name='pdf_library'),
    path('library/search/',                   views.pdf_library_search,name='pdf_library_search'),
 
    # ── PDF Tags (admin) ───────────────────────────────────────
    path('library/tags/create/',              views.pdf_tag_create,    name='pdf_tag_create'),
    path('library/tags/<int:tag_id>/delete/', views.pdf_tag_delete,    name='pdf_tag_delete'),
    path('library/tags/assign/',              views.pdf_tag_assign,    name='pdf_tag_assign'),
    path('library/tags/for-pdf/',             views.pdf_tags_for_pdf,  name='pdf_tags_for_pdf'),
 
    # ── LLM prompt (dashboard) ─────────────────────────────────
    path('prompt/',                           views.prompt_view,       name='prompt'),
    path('prompt/history/',                   views.get_chat_history,  name='get_chat_history'),
    path('prompt/clear/',                     views.clear_chat_history,name='clear_chat_history'),
 
    # ── Article pages ──────────────────────────────────────────
    path('article/<slug:slug>/',              views.article_view,      name='article'),
    path('article/<slug:slug>/json/',         views.article_json,      name='article_json'),
]