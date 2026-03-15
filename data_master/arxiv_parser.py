import os
import sys
import json
import re
from datetime import datetime, timezone

# ============================================================
#  PATHS
# ============================================================
MAIN_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR  = os.path.dirname(MAIN_DIR)
ARXIV_DIR = os.path.join(BASE_DIR, 'data', 'dumps', 'arxiv')

# Expected file layout:
#   data/dumps/arxiv/
#     arxiv-metadata-oai-snapshot.json   ← Kaggle dataset (line-delimited JSON)
#
# Download from:
#   https://www.kaggle.com/datasets/Cornell-University/arxiv
#   File: arxiv-metadata-oai-snapshot.json (~4 GB uncompressed)
#   Each line is one JSON object (NOT a JSON array)
#
# Fields we use:
#   id          → original_id  (e.g. "2103.01234")
#   title       → title
#   authors_parsed → author (first author formatted)
#   abstract    → full_text (abstracts only — no full paper PDFs)
#   categories  → categories (e.g. "cs.AI cs.LG")
#   update_date → last_updated
#
# OPTIONAL: filter to specific categories only.
# Set CATEGORY_FILTER = None to import everything.
# Set to a set of prefixes to import only those categories:
#   e.g. {'cs.AI', 'cs.LG', 'cs.CL', 'physics', 'math'}
# ============================================================

CATEGORY_FILTER = None   # None = all categories

sys.path.append(MAIN_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.utils.text import slugify
from data_master.models import Source, Document, DocumentRevision

# ============================================================
#  CONFIG
# ============================================================
BATCH_SIZE  = 1000   # larger batch — abstracts are small
REPORT_EVERY = 50000

# ============================================================
#  HELPERS
# ============================================================
_WHITESPACE = re.compile(r'\s+')

def clean_abstract(text):
    """Normalise whitespace and LaTeX artefacts in abstracts."""
    if not text:
        return ''
    # collapse whitespace and newlines within the abstract
    text = _WHITESPACE.sub(' ', text).strip()
    # remove common LaTeX markup that slips through
    text = re.sub(r'\$[^$]*\$', '[math]', text)
    text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    return text.strip()


def format_authors(authors_parsed):
    """
    authors_parsed is a list of [last, first, suffix] lists.
    Returns first author as 'First Last' string.
    """
    if not authors_parsed:
        return None
    try:
        first = authors_parsed[0]
        parts = [p for p in [first[1], first[0]] if p]
        return ' '.join(parts)
    except (IndexError, TypeError):
        return None


def make_unique_slug(arxiv_id, existing_slugs):
    """
    arXiv IDs like '2103.01234' or 'cs/0001001' are already unique.
    Use arxiv- prefix to avoid clashes.
    """
    base_slug = f'arxiv-{slugify(arxiv_id)}'[:490]
    slug      = base_slug
    counter   = 1
    while slug in existing_slugs:
        slug = f'{base_slug}-{counter}'
        counter += 1
    existing_slugs.add(slug)
    return slug


def matches_filter(categories_str):
    """Return True if any category matches CATEGORY_FILTER prefixes."""
    if CATEGORY_FILTER is None:
        return True
    cats = categories_str.split() if categories_str else []
    for cat in cats:
        for prefix in CATEGORY_FILTER:
            if cat.startswith(prefix):
                return True
    return False


def find_snapshot(arxiv_dir):
    """Find the arXiv JSON snapshot file."""
    candidates = [
        'arxiv-metadata-oai-snapshot.json',
        'arxiv-metadata.json',
    ]
    for name in candidates:
        path = os.path.join(arxiv_dir, name)
        if os.path.isfile(path):
            return path
    # fallback: any .json file in the directory
    files = [f for f in os.listdir(arxiv_dir) if f.endswith('.json')]
    if files:
        return os.path.join(arxiv_dir, files[0])
    raise FileNotFoundError(f"No arXiv JSON file found in {arxiv_dir}")


# ============================================================
#  PARSER
# ============================================================
def parse_arxiv(snapshot_path=None):
    if snapshot_path is None:
        snapshot_path = find_snapshot(ARXIV_DIR)

    print("=" * 60)
    print("  NET-1 arXiv Abstracts Parser")
    print("=" * 60)
    print(f"  File       : {os.path.basename(snapshot_path)}")
    print(f"  Filter     : {CATEGORY_FILTER or 'ALL categories'}")
    print(f"  Batch size : {BATCH_SIZE}")
    print("=" * 60)

    fname        = os.path.basename(snapshot_path)
    version_name = f"arxiv-{datetime.now().strftime('%Y-%m')}"

    source = Source.objects.create(
        name        = version_name,
        source_type = 'arxiv',
        filename    = fname,
        notes       = (
            f"Abstracts only. Loaded on {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
            f"Category filter: {CATEGORY_FILTER or 'none'}."
        )
    )
    print(f"  ✅ Source: {source.name} (ID {source.id})\n")

    # pre-load existing arXiv IDs to check for updates efficiently
    existing_ids = set(
        Document.objects.filter(source_type='arxiv')
        .values_list('original_id', flat=True)
    )
    existing_slugs = set(Document.objects.values_list('slug', flat=True))

    total_read    = 0
    total_new     = 0
    total_updated = 0
    total_skipped = 0
    total_filtered = 0

    new_batch      = []
    update_queue   = []   # (existing_doc, new_text, new_updated)
    revision_batch = []

    with open(snapshot_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            total_read += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            arxiv_id      = record.get('id', '').strip()
            title         = (record.get('title') or '').strip()
            abstract      = (record.get('abstract') or '').strip()
            categories_str = (record.get('categories') or '').strip()
            authors_parsed = record.get('authors_parsed', [])
            update_date    = record.get('update_date', '')

            if not arxiv_id or not title or not abstract:
                total_skipped += 1
                continue

            # category filter
            if not matches_filter(categories_str):
                total_filtered += 1
                continue

            full_text = (
                f"Abstract\n\n{clean_abstract(abstract)}\n\n"
                f"Categories: {categories_str}\n"
                f"arXiv ID: {arxiv_id}"
            )
            # for arXiv abstracts the full_text IS the summary
            summary = clean_abstract(abstract)[:500]

            author = format_authors(authors_parsed)

            last_updated = None
            if update_date:
                try:
                    last_updated = datetime.strptime(
                        update_date, '%Y-%m-%d'
                    ).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            if arxiv_id not in existing_ids:
                # NEW
                slug = make_unique_slug(arxiv_id, existing_slugs)
                new_batch.append(Document(
                    source_type  = 'arxiv',
                    source       = source,
                    original_id  = arxiv_id,
                    title        = title[:500],
                    slug         = slug,
                    author       = author,
                    summary      = summary,
                    full_text    = full_text,
                    categories   = categories_str,
                    language     = 'en',
                    last_updated = last_updated,
                    is_active    = True,
                ))
                total_new += 1

            else:
                # POSSIBLE UPDATE — check if abstract changed
                existing_doc = Document.objects.filter(
                    original_id = arxiv_id,
                    source_type = 'arxiv'
                ).first()
                if existing_doc and existing_doc.full_text != full_text:
                    update_queue.append((existing_doc, full_text, summary, last_updated))
                    total_updated += 1
                else:
                    total_skipped += 1

            # flush new batch
            if len(new_batch) >= BATCH_SIZE:
                Document.objects.bulk_create(new_batch, ignore_conflicts=True)
                saved = Document.objects.filter(slug__in=[d.slug for d in new_batch])
                for doc in saved:
                    revision_batch.append(DocumentRevision(
                        document=doc, source=source, version=1, diff='', previous=None,
                    ))
                new_batch = []

            # flush updates
            if len(update_queue) >= BATCH_SIZE:
                for existing_doc, new_ft, new_sum, new_lu in update_queue:
                    last_rev = DocumentRevision.objects.filter(
                        document=existing_doc
                    ).order_by('-version').first()
                    existing_doc.source       = source
                    existing_doc.summary      = new_sum
                    existing_doc.full_text    = new_ft
                    existing_doc.last_updated = new_lu
                    existing_doc.save()
                    revision_batch.append(DocumentRevision(
                        document = existing_doc,
                        source   = source,
                        version  = (last_rev.version + 1) if last_rev else 2,
                        diff     = '',
                        previous = last_rev,
                    ))
                update_queue = []

            if len(revision_batch) >= BATCH_SIZE:
                DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)
                revision_batch = []

            if total_read % REPORT_EVERY == 0:
                print(
                    f"  📖 Read: {total_read:,} | "
                    f"New: {total_new:,} | "
                    f"Updated: {total_updated:,} | "
                    f"Filtered: {total_filtered:,}"
                )

    # flush remaining
    if new_batch:
        Document.objects.bulk_create(new_batch, ignore_conflicts=True)
        for doc in Document.objects.filter(slug__in=[d.slug for d in new_batch]):
            revision_batch.append(DocumentRevision(
                document=doc, source=source, version=1, diff='', previous=None,
            ))

    if update_queue:
        for existing_doc, new_ft, new_sum, new_lu in update_queue:
            last_rev = DocumentRevision.objects.filter(
                document=existing_doc
            ).order_by('-version').first()
            existing_doc.source       = source
            existing_doc.summary      = new_sum
            existing_doc.full_text    = new_ft
            existing_doc.last_updated = new_lu
            existing_doc.save()
            revision_batch.append(DocumentRevision(
                document = existing_doc,
                source   = source,
                version  = (last_rev.version + 1) if last_rev else 2,
                diff     = '',
                previous = last_rev,
            ))

    if revision_batch:
        DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)

    source.total_documents = total_new + total_updated
    source.save()

    print("\n" + "=" * 60)
    print(f"  ✅ arXiv parse complete!")
    print(f"  Total read    : {total_read:,}")
    print(f"  New           : {total_new:,}")
    print(f"  Updated       : {total_updated:,}")
    print(f"  Unchanged     : {total_skipped:,}")
    print(f"  Filtered out  : {total_filtered:,}")
    print(f"  Source        : {source.name} (ID {source.id})")
    print("=" * 60)


if __name__ == '__main__':
    parse_arxiv()