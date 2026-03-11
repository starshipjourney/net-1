import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from data_master.models import Document
from data_master.llm import ask


# ============================================================
#  PROMPT VIEW — receives query, returns LLM response
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

        result = ask(query)
        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
#  ARTICLE JSON VIEW — returns full article content by slug
# ============================================================
@require_GET
@login_required(login_url='login')
def article_json(request, slug):
    try:
        doc = Document.objects.get(slug=slug, is_active=True)
        return JsonResponse({
            'title'      : doc.title,
            'slug'       : doc.slug,
            'author'     : doc.author,
            'source_type': doc.source_type,
            'summary'    : doc.summary,
            'full_text'  : doc.full_text,
            'categories' : doc.categories,
        })
    except Document.DoesNotExist:
        return JsonResponse({'error': 'Document not found'}, status=404)


# ============================================================
#  SEARCH VIEW — title search across all sources
# ============================================================
@require_GET
@login_required(login_url='login')
def search_view(request):
    query   = request.GET.get('q', '').strip()
    source  = request.GET.get('source', '').strip()   # optional filter: wikipedia / gutenberg
    results = []

    if query:
        qs = Document.objects.filter(
            title__icontains=query,
            is_active=True
        )
        if source:
            qs = qs.filter(source_type=source)

        results = list(
            qs.values('title', 'slug', 'summary', 'source_type', 'author')[:20]
        )

    return JsonResponse({'results': results})


# ============================================================
#  ARTICLE HTML VIEW — renders full article page
# ============================================================
@require_GET
@login_required(login_url='login')
def article_view(request, slug):
    try:
        doc = Document.objects.get(slug=slug, is_active=True)
        from django.shortcuts import render
        return render(request, 'data_master/article.html', {'article': doc})
    except Document.DoesNotExist:
        from django.http import Http404
        raise Http404