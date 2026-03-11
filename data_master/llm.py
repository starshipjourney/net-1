import re
import ollama
from django.db.models import Q
from data_master.models import Document

# ============================================================
#  CONFIG
# ============================================================
OLLAMA_HOST  = 'http://localhost:11434'
OLLAMA_MODEL = 'qwen3:8b'

client = ollama.Client(host=OLLAMA_HOST)

# ============================================================
#  BOOK QUERY DETECTION
#  Keywords that signal the user wants books/literature
# ============================================================
BOOK_KEYWORDS = {
    'book', 'novel', 'read', 'author', 'story', 'literature',
    'fiction', 'written', 'wrote', 'chapter', 'recommend',
    'recommendation', 'classic', 'tale', 'poem', 'poetry',
    'prose', 'narrative', 'adventure', 'romance',
}

def is_book_query(query):
    words = set(query.lower().split())
    return bool(words & BOOK_KEYWORDS)


# ============================================================
#  STOP WORDS — ignored in search to reduce noise
# ============================================================
STOP_WORDS = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
    'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get',
    'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now',
    'old', 'see', 'two', 'who', 'did', 'did', 'from', 'into',
    'have', 'that', 'this', 'with', 'they', 'been', 'some',
    'what', 'when', 'your', 'said', 'each', 'she', 'book',
    'about', 'need', 'want', 'looking', 'find', 'give', 'tell',
    'does', 'any', 'more', 'also', 'than', 'then', 'them',
    'these', 'those', 'would', 'could', 'should', 'there',
    'their', 'which', 'while', 'where', 'know', 'like',
}

def get_search_words(query):
    """Extract meaningful search words, filtering noise."""
    words = []
    for w in query.lower().split():
        w = w.strip('.,?!\'\"')
        if len(w) > 3 and w not in STOP_WORDS:
            words.append(w)
    return words


# ============================================================
#  PRE-SEARCH
# ============================================================
def pre_search(query, limit=8):
    """
    Search the DB for documents relevant to the query.
    If it looks like a book query, prioritise Gutenberg results.
    """
    candidates = []
    seen_ids   = set()
    book_mode  = is_book_query(query)

    def add(qs):
        for doc in qs:
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                candidates.append(doc)

    words = get_search_words(query)

    if book_mode:
        # --- BOOK QUERY: search Gutenberg first ---

        # exact phrase in book titles
        add(Document.objects.filter(
            title__icontains=query,
            source_type='gutenberg',
            is_active=True
        )[:3])

        # all meaningful words in book title (AND)
        if words:
            q = Q()
            for w in words:
                q &= Q(title__icontains=w)
            add(Document.objects.filter(
                q, source_type='gutenberg', is_active=True
            ).order_by('title')[:limit])

        # any meaningful word in book title (OR)
        if words:
            q = Q()
            for w in words:
                q |= Q(title__icontains=w)
            add(Document.objects.filter(
                q, source_type='gutenberg', is_active=True
            ).order_by('title')[:limit])

        # any word in book summary
        if words:
            q = Q()
            for w in words:
                q |= Q(summary__icontains=w)
            add(Document.objects.filter(
                q, source_type='gutenberg', is_active=True
            ).order_by('title')[:limit])

        # author name match
        if words:
            q = Q()
            for w in words:
                q |= Q(author__icontains=w)
            add(Document.objects.filter(
                q, source_type='gutenberg', is_active=True
            ).order_by('title')[:limit])

        # top up with wikipedia only if we have room
        remaining = limit - len(candidates)
        if remaining > 0 and words:
            q = Q()
            for w in words:
                q |= Q(title__icontains=w)
            add(Document.objects.filter(
                q, source_type='wikipedia', is_active=True
            ).order_by('title')[:remaining])

    else:
        # --- GENERAL QUERY: search all sources ---

        # exact phrase in title
        add(Document.objects.filter(
            title__icontains=query, is_active=True
        )[:3])

        # all words in title (AND) — high precision
        if words:
            q = Q()
            for w in words:
                q &= Q(title__icontains=w)
            add(Document.objects.filter(
                q, is_active=True
            ).order_by('title')[:limit])

        # any word in title (OR) — broader recall
        if words:
            q = Q()
            for w in words:
                q |= Q(title__icontains=w)
            add(Document.objects.filter(
                q, is_active=True
            ).order_by('title')[:limit])

        # any word in summary
        if words:
            q = Q()
            for w in words:
                q |= Q(summary__icontains=w)
            add(Document.objects.filter(
                q, is_active=True
            ).order_by('title')[:limit])

    return candidates[:limit]


# ============================================================
#  BUILD CONTEXT BLOCK
# ============================================================
def build_context(docs):
    if not docs:
        return None

    lines = ['CONTEXT — documents available in the database:\n']
    for doc in docs:
        author_part  = f' by {doc.author}' if doc.author else ''
        source_part  = f'[{doc.source_type}]'
        summary_part = (doc.summary or '')[:200]
        lines.append(
            f'- SLUG: {doc.slug}\n'
            f'  TITLE: {doc.title}{author_part} {source_part}\n'
            f'  SUMMARY: {summary_part}\n'
        )
    return '\n'.join(lines)


# ============================================================
#  PROMPT TEMPLATES
# ============================================================
SYSTEM_PROMPT = """You are NET-1, an intelligent assistant with access to a local knowledge database of Wikipedia articles and classic literature books.

Relevant documents from the database are provided as CONTEXT below.
You MUST select sources only from the CONTEXT — never invent slugs or titles.

Respond in this exact format:
SOURCES: <comma-separated slugs from context, or NONE>
ANSWER: <your answer in 2-4 sentences>

Rules:
- SOURCES: use exact slugs as shown, e.g: slug-one,slug-two
- Maximum 3 slugs, only genuinely relevant ones
- SOURCES: NONE if nothing in context is relevant
- No thinking, reasoning, or extra text
- No markdown formatting"""


SYSTEM_PROMPT_NO_CONTEXT = """You are NET-1, an intelligent assistant with access to a local knowledge database of Wikipedia articles and classic literature books.

If the query needs a knowledge article or book:
ARTICLE: <exact title>
ANSWER: <your answer in 2-4 sentences>

If conversational or needs no article:
ARTICLE: NONE
ANSWER: <your response>

Rules:
- Always use exactly this format
- No thinking, reasoning, or extra text
- No markdown formatting"""


# ============================================================
#  SLUG RESOLVER
# ============================================================
def resolve_slugs(slug_string):
    if not slug_string or slug_string.strip().upper() == 'NONE':
        return []

    slugs = [s.strip() for s in slug_string.split(',') if s.strip()]
    docs  = []
    for slug in slugs[:3]:
        try:
            doc = Document.objects.get(slug=slug, is_active=True)
            docs.append(doc)
        except Document.DoesNotExist:
            continue
    return docs


# ============================================================
#  FALLBACK SEARCH + RERANK
# ============================================================
def search_candidates(title, limit=8):
    if not title:
        return []

    candidates = []
    seen_ids   = set()

    def add(qs):
        for doc in qs:
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                candidates.append(doc)

    add(Document.objects.filter(title__iexact=title, is_active=True)[:1])
    add(Document.objects.filter(title__istartswith=title, is_active=True)[:limit])
    add(Document.objects.filter(title__icontains=title, is_active=True)[:limit])

    words = [w for w in title.split() if len(w) > 3]
    if words:
        q = Q()
        for word in words:
            q &= Q(title__icontains=word)
        add(Document.objects.filter(q, is_active=True).order_by('title')[:limit])

    return candidates[:limit]


def rerank(query, suggested_title, candidates, top_n=3):
    if not candidates:
        return []
    if len(candidates) <= top_n:
        return candidates

    candidate_list = '\n'.join(
        [f"{i+1}. {doc.title} [{doc.source_type}]" for i, doc in enumerate(candidates)]
    )

    prompt = (
        f"User query: {query}\n"
        f"Suggested title: {suggested_title}\n\n"
        f"Candidates:\n{candidate_list}\n\n"
        f"Return the numbers of the TOP {top_n} most relevant in order.\n"
        f"Reply with ONLY comma-separated numbers e.g: 1,3,2\n"
        f"If none are relevant reply with: NONE"
    )

    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1, 'num_predict': 20},
            think=False,
        )
        raw = response.message.content.strip()
        if raw.upper() == 'NONE':
            return []
        indices = []
        for part in raw.split(','):
            try:
                idx = int(part.strip()) - 1
                if 0 <= idx < len(candidates):
                    indices.append(idx)
            except ValueError:
                continue
        return [candidates[i] for i in indices[:top_n]] if indices else candidates[:top_n]
    except Exception:
        return candidates[:top_n]


# ============================================================
#  MAIN FUNCTION
# ============================================================
def ask(query):
    """
    Pipeline:
    1. Pre-search DB — book-aware, filters noise words
    2. If hits found — inject as context, LLM picks slugs
    3. If no hits — LLM suggests title, fallback rerank
    """
    try:
        context_docs = pre_search(query)
        context      = build_context(context_docs)

        if context:
            user_message = f"{context}\n\nUser query: {query}"

            response = client.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user',   'content': user_message},
                ],
                options={'temperature': 0.3, 'num_predict': 400},
                think=False,
            )

            raw    = response.message.content.strip()
            parsed = _parse_context_response(raw)

            top_docs = resolve_slugs(parsed['sources'])

            # fallback — LLM said NONE but we had context, use top results
            if not top_docs and context_docs:
                top_docs = context_docs[:3]

        else:
            # no pre-search hits — LLM suggests title blindly
            response = client.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT_NO_CONTEXT},
                    {'role': 'user',   'content': query},
                ],
                options={'temperature': 0.3, 'num_predict': 300},
                think=False,
            )

            raw    = response.message.content.strip()
            parsed = _parse_no_context_response(raw)

            needs_article = parsed.get('article_title') not in (None, 'NONE', 'none', '')

            if not needs_article:
                return {
                    'answer'       : parsed['answer'],
                    'sources'      : [],
                    'found'        : False,
                    'needs_article': False,
                }

            candidates = search_candidates(parsed['article_title'])
            top_docs   = rerank(query, parsed['article_title'], candidates)

        sources = [
            {
                'title'      : doc.title,
                'slug'       : doc.slug,
                'summary'    : doc.summary,
                'source_type': doc.source_type,
                'author'     : doc.author,
            }
            for doc in top_docs
        ]

        return {
            'answer'       : parsed['answer'],
            'sources'      : sources,
            'found'        : len(sources) > 0,
            'needs_article': True,
        }

    except Exception as e:
        return {
            'answer'       : f'ERROR: Could not connect to LLM — {str(e)}',
            'sources'      : [],
            'found'        : False,
            'needs_article': False,
        }


# ============================================================
#  RESPONSE PARSERS
# ============================================================
def _parse_context_response(raw):
    sources = None
    answer  = None

    sources_match = re.search(r'SOURCES:\s*(.+)', raw)
    if sources_match:
        sources = sources_match.group(1).strip()

    answer_match = re.search(r'ANSWER:\s*(.+)', raw, re.DOTALL)
    if answer_match:
        answer = answer_match.group(1).strip()

    if not answer:
        answer = raw

    return {'answer': answer, 'sources': sources}


def _parse_no_context_response(raw):
    article_title = None
    answer        = None

    article_match = re.search(r'ARTICLE:\s*(.+)', raw)
    if article_match:
        article_title = article_match.group(1).strip()

    answer_match = re.search(r'ANSWER:\s*(.+)', raw, re.DOTALL)
    if answer_match:
        answer = answer_match.group(1).strip()

    if not answer:
        answer = raw

    return {'answer': answer, 'article_title': article_title}