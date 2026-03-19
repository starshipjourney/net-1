import re
import json
import ollama
import django.conf
from django.db.models import Q
from data_master.models import Document

# ============================================================
#  CONFIG
# ============================================================
OLLAMA_HOST  = getattr(django.conf.settings, 'OLLAMA_HOST',  'http://localhost:11434')
OLLAMA_MODEL = getattr(django.conf.settings, 'OLLAMA_MODEL', 'qwen3:8b')

client = ollama.Client(host=OLLAMA_HOST)

# ============================================================
#  VALKEY — conversation history
# ============================================================
HISTORY_TTL     = 60 * 60 * 24 * 7   # 7 days
HISTORY_MAX     = 20                   # max turns kept in Valkey
CONTEXT_WINDOW  = 10                   # turns sent to LLM each time

try:
    from django_valkey import get_valkey_connection
    _vk = get_valkey_connection('default')
    _vk.ping()
    VALKEY_OK = True
except Exception:
    _vk       = None
    VALKEY_OK  = False


def _history_key(user_id):
    return f'net1:chat:{user_id}'


def get_history(user_id):
    """Return list of {role, content} dicts for this user."""
    if not _vk:
        return []
    try:
        raw = _vk.get(_history_key(user_id))
        return json.loads(raw) if raw else []
    except Exception:
        return []


def save_history(user_id, history):
    """Persist trimmed history to Valkey."""
    if not _vk:
        return
    try:
        trimmed = history[-HISTORY_MAX:]
        _vk.set(_history_key(user_id), json.dumps(trimmed), ex=HISTORY_TTL)
    except Exception:
        pass


def clear_history(user_id):
    """Wipe conversation history for this user."""
    if not _vk:
        return
    try:
        _vk.delete(_history_key(user_id))
    except Exception:
        pass


# ============================================================
#  SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT = """You are NET-1, an intelligent offline assistant.

You have broad general knowledge and can help with anything — conversation,
reasoning, maths, coding, writing, advice, analysis, and more.

You also have access to a local knowledge library containing:
  - Wikipedia articles
  - Wikibooks textbooks
  - Wikivoyage travel guides
  - Project Gutenberg classic literature
  - iFixit repair and how-to guides
  - arXiv scientific research abstracts

When relevant library documents are provided as CONTEXT, use them to enrich
your answer. Reference them naturally if helpful — but never force them in.

You remember the conversation history and refer back to it naturally when relevant.

If CONTEXT is provided, end your response with this line only when genuinely useful:
SOURCES: slug-one, slug-two

Rules:
- Talk naturally. Be helpful, clear, and conversational.
- Answer questions directly — do not say "based on the context" or "according to".
- Only include SOURCES if the documents actually helped your answer.
- If no documents are relevant, omit the SOURCES line entirely.
- Never invent slugs. Only use slugs exactly as shown in CONTEXT.
- No XML tags, no markdown headers, no robotic formatting.
- Respond in the same language the user writes in."""


# ============================================================
#  STOP WORDS
# ============================================================
STOP_WORDS = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
    'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get',
    'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now',
    'old', 'see', 'two', 'who', 'did', 'from', 'into', 'have',
    'that', 'this', 'with', 'they', 'been', 'some', 'what',
    'when', 'your', 'said', 'each', 'she', 'about', 'need',
    'want', 'looking', 'find', 'give', 'tell', 'does', 'any',
    'more', 'also', 'than', 'then', 'them', 'these', 'those',
    'would', 'could', 'should', 'there', 'their', 'which',
    'while', 'where', 'know', 'like', 'just', 'very', 'much',
}

_BOOK_KW     = {'book','novel','read','author','story','literature','fiction',
                'written','wrote','chapter','classic','tale','poem','poetry',
                'prose','narrative','adventure','romance','recommend'}
_REPAIR_KW   = {'repair','fix','broken','replace','install','disassemble',
                'teardown','guide','manual','screen','battery',
                'keyboard','laptop','phone','iphone','macbook','device','hardware'}
_RESEARCH_KW = {'research','paper','study','abstract','arxiv','journal',
                'algorithm','neural','dataset','experiment','findings',
                'analysis','theorem','published','methodology'}
_TRAVEL_KW   = {'travel','visit','trip','tourism','tourist','destination',
                'hotel','flight','airport','itinerary','vacation','holiday',
                'backpack','hostel','attractions','passport','visa'}
_LEARN_KW    = {'learn','explain','understand','definition','concept','theory',
                'textbook','course','lesson','introduction','basics',
                'overview','fundamentals','examples','exercises'}


def _words(text):
    return set(w.strip('.,?!\'"') for w in text.lower().split())


def _priority_sources(query):
    w = _words(query)
    if w & _REPAIR_KW:   return ['ifixit',    'wikipedia']
    if w & _RESEARCH_KW: return ['arxiv',      'wikipedia']
    if w & _TRAVEL_KW:   return ['wikivoyage', 'wikipedia']
    if w & _BOOK_KW:     return ['gutenberg',  'wikibooks', 'wikipedia']
    if w & _LEARN_KW:    return ['wikibooks',  'wikipedia']
    return ['wikipedia', 'wikibooks', 'wikivoyage', 'gutenberg', 'ifixit', 'arxiv']


def _search_words(query):
    return [w for w in _words(query) if len(w) > 3 and w not in STOP_WORDS]


# ============================================================
#  QUERY CLASSIFIER
# ============================================================
_CONVERSATIONAL = re.compile(
    r'^(hi|hello|hey|thanks|thank you|good morning|good evening|how are you|'
    r"what's up|sup|ok|okay|sure|yes|no|bye|goodbye|lol|haha|cool|nice|great|"
    r'awesome|perfect|got it|i see|makes sense|interesting|wow|really)',
    re.IGNORECASE
)

def _should_search(query):
    q = query.strip()
    if len(q) < 12:
        return False
    if re.match(r'^[\d\s\+\-\*\/\^\(\)\.=]+$', q):
        return False
    if len(q) < 40 and _CONVERSATIONAL.match(q):
        return False
    return True


# ============================================================
#  PRE-SEARCH
# ============================================================
def pre_search(query, limit=6):
    candidates = []
    seen_ids   = set()
    words      = _search_words(query)
    sources    = _priority_sources(query)

    if not words:
        return []

    def add(qs):
        for doc in qs:
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                candidates.append(doc)

    primary   = sources[:2]
    secondary = sources[2:]

    for source_group in [primary, secondary]:
        if len(candidates) >= limit:
            break
        remaining = limit - len(candidates)

        add(Document.objects.filter(
            title__icontains=query,
            source_type__in=source_group,
            is_active=True
        )[:2])

        if words and len(candidates) < limit:
            q_obj = Q()
            for w in words:
                q_obj &= Q(title__icontains=w)
            add(Document.objects.filter(
                q_obj, source_type__in=source_group, is_active=True
            ).order_by('title')[:remaining])

        if words and len(candidates) < limit:
            q_obj = Q()
            for w in words:
                q_obj |= Q(title__icontains=w)
            add(Document.objects.filter(
                q_obj, source_type__in=source_group, is_active=True
            ).order_by('title')[:remaining])

        if words and len(candidates) < limit:
            q_obj = Q()
            for w in words:
                q_obj |= Q(summary__icontains=w)
            add(Document.objects.filter(
                q_obj, source_type__in=source_group, is_active=True
            ).order_by('title')[:remaining])

        if words and len(candidates) < limit:
            q_obj = Q()
            for w in words:
                q_obj |= Q(author__icontains=w)
            add(Document.objects.filter(
                q_obj, source_type__in=source_group, is_active=True
            ).order_by('title')[:remaining])

    return candidates[:limit]


# ============================================================
#  BUILD CONTEXT BLOCK
# ============================================================
def build_context(docs):
    if not docs:
        return None
    lines = ['CONTEXT — documents from your local library:\n']
    for doc in docs:
        author_part  = f' by {doc.author}' if doc.author else ''
        summary_part = (doc.summary or '')[:300]
        lines.append(
            f'- SLUG: {doc.slug}\n'
            f'  [{doc.source_type.upper()}] {doc.title}{author_part}\n'
            f'  {summary_part}\n'
        )
    return '\n'.join(lines)


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
            docs.append(Document.objects.get(slug=slug, is_active=True))
        except Document.DoesNotExist:
            continue
    return docs


# ============================================================
#  MAIN FUNCTION
# ============================================================
def ask(query, user_id=None):
    """
    Conversational pipeline with Valkey-backed history.
    user_id: Django user pk — used to key the conversation in Valkey.
             If None, history is not persisted (anonymous/fallback).
    """
    try:
        # ── load history from Valkey ──
        history  = get_history(user_id) if user_id else []

        # ── search DB for relevant docs ──
        context_docs = []
        if _should_search(query):
            context_docs = pre_search(query)

        # ── build user message (with optional context) ──
        if context_docs:
            context      = build_context(context_docs)
            user_message = f"{context}\n\nUser: {query}"
        else:
            user_message = query

        # ── assemble messages for LLM ──
        # system prompt → recent history → current user message
        recent   = history[-CONTEXT_WINDOW:]
        messages = (
            [{'role': 'system', 'content': SYSTEM_PROMPT}]
            + recent
            + [{'role': 'user', 'content': user_message}]
        )

        # ── call LLM ──
        response = client.chat(
            model   = OLLAMA_MODEL,
            messages= messages,
            options = {'temperature': 0.7, 'num_predict': 600},
            think   = False,
        )

        raw    = response.message.content.strip()
        parsed = _parse_response(raw)
        answer = parsed['answer']

        # ── resolve sources ──
        top_docs = resolve_slugs(parsed['sources'])
        if not top_docs and context_docs and _explicitly_wants_source(query):
            top_docs = context_docs[:1]

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

        # ── persist turn to Valkey ──
        # store clean query (not the context-injected version)
        # store clean answer (no SOURCES line)
        if user_id:
            history.append({'role': 'user',      'content': query})
            history.append({'role': 'assistant', 'content': answer})
            save_history(user_id, history)

        return {
            'answer' : answer,
            'sources': sources,
            'found'  : len(sources) > 0,
        }

    except Exception as e:
        return {
            'answer' : f'Something went wrong connecting to the LLM — {str(e)}',
            'sources': [],
            'found'  : False,
        }


def _explicitly_wants_source(query):
    triggers = {
        'find', 'show', 'search', 'article', 'book', 'read', 'guide',
        'paper', 'source', 'reference', 'look up', 'recommend', 'suggest',
        'what is', 'who is', 'tell me about',
    }
    q = query.lower()
    return any(t in q for t in triggers)


# ============================================================
#  RESPONSE PARSER
# ============================================================
def _parse_response(raw):
    sources_match = re.search(r'\bSOURCES:\s*(.+?)(?:\n|$)', raw, re.IGNORECASE)
    if sources_match:
        sources = sources_match.group(1).strip()
        answer  = raw[:sources_match.start()].strip()
    else:
        sources = None
        answer  = raw.strip()
    return {'answer': answer, 'sources': sources}