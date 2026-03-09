import re
import ollama
from django.db.models import Q
from data_master.models import WikiPage

# ============================================================
#  CONFIG
# ============================================================
OLLAMA_HOST  = 'http://localhost:11434'
OLLAMA_MODEL = 'qwen3:8b'

client = ollama.Client(host=OLLAMA_HOST)

# ============================================================
#  PROMPT TEMPLATES
# ============================================================
SYSTEM_PROMPT = """You are NET-1, an intelligent assistant with access to a local Wikipedia database.

When a user asks a question or makes a request, decide if it requires a knowledge article or not.

If the question requires a knowledge article (factual, historical, scientific, biographical questions):
ARTICLE: <exact Wikipedia article title — use the most specific subject, e.g. "Alexander Graham Bell" not "Telephone">
ANSWER: <your answer in 2-4 sentences>

If the question is conversational, mathematical, or does not need an article:
ARTICLE: NONE
ANSWER: <your response>

Examples:
User: "Who invented the telephone?"
ARTICLE: Alexander Graham Bell
ANSWER: Alexander Graham Bell invented the telephone in 1876...

User: "What is 25 times 4?"
ARTICLE: NONE
ANSWER: 25 times 4 is 100.

Rules:
- Always use exactly this format, no exceptions
- ARTICLE must be the most specific Wikipedia article title possible
- Do not include any thinking, reasoning, or extra text
- Do not use markdown formatting"""


RERANK_PROMPT = """You are helping match a user query to the most relevant Wikipedia article.

User query: {query}
Suggested article: {suggested}

Here are the candidate articles found in the database:
{candidates}

Which candidate is the most relevant to the user query?
Reply with ONLY the exact title of the best matching article, nothing else.
If none are relevant, reply with: NONE"""


# ============================================================
#  ARTICLE SEARCH — returns multiple candidates
# ============================================================
def search_candidates(title, limit=5):
    """
    Search PostgreSQL for candidate articles matching the title.
    Returns a list of WikiPage objects.
    """
    if not title:
        return []

    candidates = []
    seen_ids   = set()

    def add(qs):
        for a in qs:
            if a.id not in seen_ids:
                seen_ids.add(a.id)
                candidates.append(a)

    # exact match
    add(WikiPage.objects.filter(title__iexact=title, is_active=True)[:1])

    # starts with
    add(WikiPage.objects.filter(title__istartswith=title, is_active=True)[:limit])

    # full phrase contains
    add(WikiPage.objects.filter(title__icontains=title, is_active=True)[:limit])

    # all words must appear
    words = [w for w in title.split() if len(w) > 3]
    if words:
        query = Q()
        for word in words:
            query &= Q(title__icontains=word)
        add(WikiPage.objects.filter(query, is_active=True).order_by('title')[:limit])

    return candidates[:limit]


# ============================================================
#  RERANKER — LLM picks best candidate
# ============================================================
def rerank(query, suggested_title, candidates):
    """
    Ask the LLM to pick the best article from candidates.
    Returns the winning WikiPage or None.
    """
    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    candidate_list = '\n'.join(
        [f"{i+1}. {a.title}" for i, a in enumerate(candidates)]
    )

    prompt = RERANK_PROMPT.format(
        query     = query,
        suggested = suggested_title,
        candidates= candidate_list,
    )

    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1, 'num_predict': 50},
            think=False,
        )

        chosen_title = response.message.content.strip()

        if chosen_title.upper() == 'NONE':
            return None

        # find the chosen title in candidates
        for article in candidates:
            if article.title.lower() == chosen_title.lower():
                return article

        # fuzzy fallback — LLM may have slightly altered the title
        for article in candidates:
            if chosen_title.lower() in article.title.lower():
                return article

        # default to first candidate if no match
        return candidates[0]

    except Exception:
        return candidates[0]


# ============================================================
#  MAIN FUNCTION
# ============================================================
def ask(query):
    """
    Full pipeline:
    1. LLM answers query and suggests article title
    2. PostgreSQL search for candidates
    3. LLM reranks candidates to pick best match
    4. Return answer + best article
    """
    try:
        # stage 1 — LLM answers + suggests title
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user',   'content': query},
            ],
            options={'temperature': 0.3, 'num_predict': 300},
            think=False,
        )

        raw    = response.message.content.strip()
        parsed = _parse_response(raw)

        needs_article = parsed['article_title'] not in (None, 'NONE', 'none', '')

        if not needs_article:
            return {
                'answer'         : parsed['answer'],
                'article_title'  : None,
                'article_slug'   : None,
                'article_summary': None,
                'found'          : False,
                'needs_article'  : False,
            }

        # stage 2 — search PostgreSQL for candidates
        candidates = search_candidates(parsed['article_title'])

        # stage 3 — LLM reranks candidates
        article = rerank(query, parsed['article_title'], candidates)

        return {
            'answer'         : parsed['answer'],
            'article_title'  : article.title   if article else parsed['article_title'],
            'article_slug'   : article.slug    if article else None,
            'article_summary': article.summary if article else None,
            'found'          : article is not None,
            'needs_article'  : True,
        }

    except Exception as e:
        return {
            'answer'         : f'ERROR: Could not connect to LLM — {str(e)}',
            'article_title'  : None,
            'article_slug'   : None,
            'article_summary': None,
            'found'          : False,
            'needs_article'  : False,
        }


# ============================================================
#  RESPONSE PARSER
# ============================================================
def _parse_response(raw):
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

    return {
        'answer'       : answer,
        'article_title': article_title,
    }