import os
import json
from pathlib import Path
from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.conf import settings
from data_master.models import Document, PdfTag, PdfTagAssignment
from data_master.llm import ask
from data_master import pdf_thumbs

# ============================================================
#  PATHS — read from settings for container compatibility
# ============================================================
PDF_DIR = Path(getattr(settings, 'PDF_DIR', Path(settings.BASE_DIR).parent / 'data' / 'pdfs'))

# ============================================================
#  SOURCE META
# ============================================================
SOURCE_META = {
    'wikipedia' : {'icon': '📄', 'label': 'Wikipedia',  'colour': '#4a6fa5'},
    'wikibooks' : {'icon': '📚', 'label': 'Wikibooks',  'colour': '#c07a20'},
    'wikivoyage': {'icon': '🗺️', 'label': 'Wikivoyage', 'colour': '#3a6888'},
    'gutenberg' : {'icon': '📖', 'label': 'Gutenberg',  'colour': '#2a8050'},
    'ifixit'    : {'icon': '🔧', 'label': 'iFixit',     'colour': '#b03030'},
    'arxiv'     : {'icon': '🔬', 'label': 'arXiv',      'colour': '#7048c8'},
}

# ============================================================
#  PDF SCANNER
# ============================================================
def scan_pdfs(query=''):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = []

    for path in sorted(PDF_DIR.glob('**/*.pdf')):
        name = path.stem.replace('-', ' ').replace('_', ' ').title()

        if query and query.lower() not in name.lower() \
                 and query.lower() not in path.name.lower():
            continue

        size_bytes = path.stat().st_size
        if size_bytes < 1024:
            size_str = f'{size_bytes} B'
        elif size_bytes < 1024 * 1024:
            size_str = f'{size_bytes / 1024:.0f} KB'
        else:
            size_str = f'{size_bytes / (1024*1024):.1f} MB'

        rel      = path.relative_to(PDF_DIR)
        parts    = rel.parts
        category = parts[0] if len(parts) > 1 else 'General'

        # generate thumbnail if it doesn't exist yet
        thumb_url = pdf_thumbs.get_thumbnail_url(str(rel))
        if not thumb_url:
            result    = pdf_thumbs.generate_thumbnail(path)
            thumb_url = pdf_thumbs.get_thumbnail_url(str(rel)) if result else None

        pdfs.append({
            'name'     : name,
            'filename' : str(rel),
            'category' : category,
            'size'     : size_str,
            'modified' : path.stat().st_mtime,
            'thumb_url': thumb_url,
        })

    return pdfs


# ============================================================
#  CATALOGUE
# ============================================================
@login_required(login_url='login')
def catalogue_view(request):
    source_counts = {
        src: Document.objects.filter(source_type=src, is_active=True).count()
        for src in SOURCE_META
    }
    pdf_count  = len(list(PDF_DIR.glob('**/*.pdf'))) if PDF_DIR.exists() else 0
    total_docs = sum(source_counts.values())

    return render(request, 'data_master/catalogue.html', {
        'source_meta'   : SOURCE_META,
        'source_counts' : source_counts,
        'pdf_count'     : pdf_count,
        'total_docs'    : total_docs,
    })


@require_GET
@login_required(login_url='login')
def catalogue_search(request):
    query          = request.GET.get('q', '').strip()
    sources_param  = request.GET.get('sources', '')   # comma-separated, empty = all
    tab            = request.GET.get('tab', 'all')
    page           = int(request.GET.get('page', 1))
    per_page       = 40

    # parse multi-source filter — exclude __pdf__ (handled separately)
    selected_sources = [
        s.strip() for s in sources_param.split(',')
        if s.strip() and s.strip() != '__pdf__'
    ]
    pdf_selected = '__pdf__' in sources_param

    results = {'documents': [], 'pdfs': [], 'total_docs': 0, 'total_pdfs': 0}

    # if only PDFs selected, skip DB entirely
    skip_docs = pdf_selected and not selected_sources and sources_param != ''

    # ── DB documents ──
    if tab != 'pdfs' and not skip_docs:
        qs = Document.objects.filter(is_active=True)
        if selected_sources:
            qs = qs.filter(source_type__in=selected_sources)
        if query:
            qs = qs.filter(
                Q(title__icontains=query) |
                Q(summary__icontains=query) |
                Q(author__icontains=query)
            )
        else:
            qs = qs.order_by('?')

        total_docs      = qs.count()
        offset          = (page - 1) * per_page
        docs            = qs.values(
            'title', 'slug', 'summary', 'source_type', 'author', 'categories'
        )[offset: offset + per_page]

        results['total_docs'] = total_docs
        results['documents']  = [
            {
                **dict(d),
                'icon'   : SOURCE_META.get(d['source_type'], {}).get('icon', '📄'),
                'colour' : SOURCE_META.get(d['source_type'], {}).get('colour', '#888'),
                'label'  : SOURCE_META.get(d['source_type'], {}).get('label', d['source_type']),
                'summary': (d['summary'] or '')[:180],
            }
            for d in docs
        ]

    # ── PDFs ──
    show_pdfs = tab != 'docs' and (not sources_param or pdf_selected or not selected_sources)
    if show_pdfs:
        pdfs                  = scan_pdfs(query)
        results['total_pdfs'] = len(pdfs)
        offset                = (page - 1) * per_page
        results['pdfs']       = pdfs[offset: offset + per_page]

    return JsonResponse(results)


@xframe_options_exempt
@require_GET
@login_required(login_url='login')
def serve_pdf(request, filepath):
    safe = Path(filepath).parts
    if '..' in safe:
        raise Http404
    full_path = PDF_DIR / filepath
    if not full_path.exists() or full_path.suffix.lower() != '.pdf':
        raise Http404
    response = FileResponse(
        open(full_path, 'rb'),
        content_type='application/pdf',
    )
    # inline — tells browser to display in iframe, not download
    response['Content-Disposition'] = f'inline; filename="{full_path.name}"' 
    # allow embedding in our own iframe
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


# ============================================================
#  SERVE PDF THUMBNAIL
# ============================================================
@require_GET
@login_required(login_url='login')
def serve_thumb(request, filename):
    """Serve a cached PDF thumbnail."""
    from data_master.pdf_thumbs import THUMB_DIR
    safe = Path(filename).name   # strip any path — just filename
    thumb_path = THUMB_DIR / safe
    if not thumb_path.exists() or thumb_path.suffix != '.webp':
        raise Http404
    return FileResponse(open(thumb_path, 'rb'), content_type='image/webp')


# ============================================================
#  GENERATE THUMBNAIL ON DEMAND
# ============================================================
@require_GET
@login_required(login_url='login')
def generate_thumb(request, filepath):
    """
    Generate a thumbnail for a PDF on demand (called by catalogue JS).
    Returns JSON with thumb_url or null.
    """
    safe = Path(filepath).parts
    if '..' in safe:
        return JsonResponse({'thumb_url': None})

    from data_master.pdf_thumbs import PDF_DIR, generate_thumbnail, get_thumbnail_url
    full_path = PDF_DIR / filepath
    if not full_path.exists():
        return JsonResponse({'thumb_url': None})

    generate_thumbnail(full_path)
    url = get_thumbnail_url(filepath)
    return JsonResponse({'thumb_url': url})


# ============================================================
#  PROMPT (LLM)
# ============================================================
@csrf_exempt
@require_POST
@login_required(login_url='login')
def prompt_view(request):
    try:
        body  = json.loads(request.body)
        query = body.get('query', '').strip()
        if not query:
            return JsonResponse({'error': 'No query provided'}, status=400)
        result = ask(query, user_id=request.user.pk)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
#  CHAT HISTORY ENDPOINTS
# ============================================================
@require_GET
@login_required(login_url='login')
def get_chat_history(request):
    """Return the user's conversation history for UI restore."""
    from data_master.llm import get_history
    raw_history = get_history(request.user.pk)

    # convert LLM format {role, content} → UI format {role, text, sources, codeBlocks}
    ui_history = []
    for msg in raw_history:
        if msg['role'] == 'user':
            ui_history.append({
                'role'      : 'user',
                'text'      : msg['content'],
                'sources'   : [],
                'codeBlocks': None,
            })
        else:
            ui_history.append({
                'role'      : 'net1',
                'text'      : msg['content'],
                'sources'   : [],
                'codeBlocks': None,
            })

    return JsonResponse({'history': ui_history})


@require_POST
@login_required(login_url='login')
def clear_chat_history(request):
    """Wipe the user's conversation history from Valkey."""
    from data_master.llm import clear_history
    clear_history(request.user.pk)
    return JsonResponse({'ok': True})


# ============================================================
#  ARTICLE
# ============================================================
@require_GET
@login_required(login_url='login')
def article_view(request, slug):
    try:
        doc        = Document.objects.get(slug=slug, is_active=True)
        ref_text   = request.GET.get('ref', '')
        return render(request, 'data_master/article.html', {
            'article' : doc,
            'ref_text': ref_text,
        })
    except Document.DoesNotExist:
        raise Http404


@require_GET
@login_required(login_url='login')
def article_json(request, slug):
    try:
        doc = Document.objects.get(slug=slug, is_active=True)
        return JsonResponse({
            'title'      : doc.title,
            'slug'       : doc.slug,
            'summary'    : doc.summary,
            'full_text'  : doc.full_text,
            'categories' : doc.categories,
            'author'     : doc.author,
            'source_type': doc.source_type,
        })
    except Document.DoesNotExist:
        raise Http404


# ============================================================
#  REF SEARCH (notes editor)
# ============================================================
@require_GET
@login_required(login_url='login')
def ref_search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    docs = Document.objects.filter(
        Q(title__icontains=query) |
        Q(summary__icontains=query) |
        Q(author__icontains=query),
        is_active=True
    ).values(
        'id', 'title', 'author', 'source_type', 'slug', 'summary'
    )[:20]

    results = []
    for doc in docs:
        try:
            full = Document.objects.get(id=doc['id'])
            doc['full_text'] = (full.full_text or '')[:8000]
        except Exception:
            doc['full_text'] = ''
        results.append(doc)

    return JsonResponse({'results': results})


# ============================================================
#  PDF LIBRARY  (catalogue tab with tagging sidebar)
# ============================================================
@login_required(login_url='login')
def pdf_library_view(request):
    """Dedicated PDF library page with tag sidebar."""
    tags      = PdfTag.objects.all()
    pdf_count = len(list(PDF_DIR.glob('**/*.pdf'))) if PDF_DIR.exists() else 0

    return render(request, 'data_master/pdf_library.html', {
        'tags'        : tags,
        'pdf_count'   : pdf_count,
        'is_admin'    : request.user.is_staff or request.user.is_superuser,
        'colour_list' : [
            '#f59e0b','#ef4444','#3b82f6','#10b981',
            '#8b5cf6','#ec4899','#f97316','#06b6d4',
            '#84cc16','#6366f1',
        ],
    })


@require_GET
@login_required(login_url='login')
def pdf_library_search(request):
    """AJAX — returns PDFs filtered by tag and/or query."""
    query    = request.GET.get('q', '').strip()
    tag_slug = request.GET.get('tag', '').strip()
    page     = int(request.GET.get('page', 1))
    per_page = 40

    # get all PDFs from disk
    all_pdfs = scan_pdfs(query)

    # filter by tag if specified
    if tag_slug and tag_slug != 'all':
        if tag_slug == 'untagged':
            # show PDFs with zero tag assignments
            all_assigned = set(
                PdfTagAssignment.objects.values_list('pdf_path', flat=True)
            )
            all_pdfs = [p for p in all_pdfs if p['filename'] not in all_assigned]
        else:
            try:
                tag      = PdfTag.objects.get(slug=tag_slug)
                assigned = set(
                    PdfTagAssignment.objects.filter(tag=tag)
                    .values_list('pdf_path', flat=True)
                )
                all_pdfs = [p for p in all_pdfs if p['filename'] in assigned]
            except PdfTag.DoesNotExist:
                all_pdfs = []

    # annotate each PDF with its tags
    all_paths    = [p['filename'] for p in all_pdfs]
    assignments  = PdfTagAssignment.objects.filter(
        pdf_path__in=all_paths
    ).select_related('tag')

    tags_by_pdf = {}
    for a in assignments:
        tags_by_pdf.setdefault(a.pdf_path, []).append({
            'name'  : a.tag.name,
            'slug'  : a.tag.slug,
            'colour': a.tag.colour,
            'icon'  : a.tag.icon,
        })

    for pdf in all_pdfs:
        pdf['tags'] = tags_by_pdf.get(pdf['filename'], [])

    total  = len(all_pdfs)
    offset = (page - 1) * per_page

    return JsonResponse({
        'pdfs'      : all_pdfs[offset: offset + per_page],
        'total_pdfs': total,
    })


# ── Tag management (admin only) ──────────────────────────────

@require_POST
@login_required(login_url='login')
def pdf_tag_create(request):
    """Create a new PDF tag — admin only."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)
    try:
        data   = json.loads(request.body)
        name   = data.get('name', '').strip()
        colour = data.get('colour', '#f59e0b')
        icon   = data.get('icon', '🏷️')
        desc   = data.get('description', '')

        if not name:
            return JsonResponse({'error': 'Name required'}, status=400)

        from django.utils.text import slugify
        tag, created = PdfTag.objects.get_or_create(
            slug=slugify(name),
            defaults={
                'name'       : name,
                'colour'     : colour,
                'icon'       : icon,
                'description': desc,
                'created_by' : request.user,
            }
        )
        if not created:
            return JsonResponse({'error': 'Tag already exists'}, status=400)

        return JsonResponse({
            'id'    : tag.id,
            'name'  : tag.name,
            'slug'  : tag.slug,
            'colour': tag.colour,
            'icon'  : tag.icon,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required(login_url='login')
def pdf_tag_delete(request, tag_id):
    """Delete a tag — admin only."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)
    try:
        PdfTag.objects.filter(id=tag_id).delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required(login_url='login')
def pdf_tag_assign(request):
    """Assign/unassign a tag to a PDF — admin only."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Admin only'}, status=403)
    try:
        data     = json.loads(request.body)
        tag_id   = data.get('tag_id')
        pdf_path = data.get('pdf_path', '').strip()
        pdf_name = data.get('pdf_name', '').strip()
        action   = data.get('action', 'assign')   # 'assign' | 'unassign'

        if not tag_id or not pdf_path:
            return JsonResponse({'error': 'tag_id and pdf_path required'}, status=400)

        tag = PdfTag.objects.get(id=tag_id)

        if action == 'assign':
            PdfTagAssignment.objects.get_or_create(
                tag      = tag,
                pdf_path = pdf_path,
                defaults = {
                    'pdf_name'   : pdf_name,
                    'assigned_by': request.user,
                }
            )
        else:
            PdfTagAssignment.objects.filter(tag=tag, pdf_path=pdf_path).delete()

        return JsonResponse({'ok': True})
    except PdfTag.DoesNotExist:
        return JsonResponse({'error': 'Tag not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
@login_required(login_url='login')
def pdf_tags_for_pdf(request):
    """Return all tags assigned to a given PDF path."""
    pdf_path    = request.GET.get('pdf_path', '').strip()
    assignments = PdfTagAssignment.objects.filter(
        pdf_path=pdf_path
    ).select_related('tag')

    all_tags     = PdfTag.objects.all()
    assigned_ids = set(a.tag_id for a in assignments)

    return JsonResponse({
        'assigned': [
            {'id': a.tag.id, 'name': a.tag.name,
             'slug': a.tag.slug, 'colour': a.tag.colour, 'icon': a.tag.icon}
            for a in assignments
        ],
        'all_tags': [
            {'id': t.id, 'name': t.name, 'slug': t.slug,
             'colour': t.colour, 'icon': t.icon,
             'assigned': t.id in assigned_ids}
            for t in all_tags
        ],
    })