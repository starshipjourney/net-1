import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from data_master.models import WikiPage
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
        article = WikiPage.objects.get(slug=slug, is_active=True)
        return JsonResponse({
            'title'     : article.title,
            'slug'      : article.slug,
            'summary'   : article.summary,
            'full_text' : article.full_text,
            'categories': article.categories,
        })
    except WikiPage.DoesNotExist:
        return JsonResponse({'error': 'Article not found'}, status=404)


# ============================================================
#  SEARCH VIEW — basic title search
# ============================================================
@require_GET
@login_required(login_url='login')
def search_view(request):
    query    = request.GET.get('q', '').strip()
    results  = []

    if query:
        articles = WikiPage.objects.filter(
            title__icontains=query,
            is_active=True
        ).values('title', 'slug', 'summary')[:20]
        results = list(articles)

    return JsonResponse({'results': results})


# ============================================================
#  ARTICLE HTML VIEW — renders full article page
# ============================================================
@require_GET
@login_required(login_url='login')
def article_view(request, slug):
    try:
        article = WikiPage.objects.get(slug=slug, is_active=True)
        from django.shortcuts import render
        return render(request, 'data_master/article.html', {'article': article})
    except WikiPage.DoesNotExist:
        from django.http import Http404
        raise Http404