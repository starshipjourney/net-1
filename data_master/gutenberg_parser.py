import os
import sys
import re
import csv
from datetime import datetime, timezone

# ============================================================
#  PATHS
# ============================================================
MAIN_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR  = os.path.dirname(MAIN_DIR)
BOOKS_DIR = os.path.join(BASE_DIR, 'data', 'dumps', 'gutenberg', 'books')
META_PATH = os.path.join(BASE_DIR, 'data', 'dumps', 'gutenberg', 'pg_catalog.csv')

# Django setup
sys.path.append(MAIN_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.utils.text import slugify
from data_master.models import Source, Document, DocumentRevision

# ============================================================
#  CONFIG
# ============================================================
BATCH_SIZE = 50

# ============================================================
#  TEXT CLEANING
# ============================================================

# Gutenberg header ends at one of these markers
_HEADER_END = re.compile(
    r'\*\*\*\s*START OF TH(E|IS) PROJECT GUTENBERG',
    re.IGNORECASE
)

# Gutenberg footer starts at one of these markers
_FOOTER_START = re.compile(
    r'\*\*\*\s*END OF TH(E|IS) PROJECT GUTENBERG',
    re.IGNORECASE
)

def clean_book_text(raw):
    """
    Strip Gutenberg header and footer boilerplate.
    Returns clean book content only.
    """
    # strip header
    header_match = _HEADER_END.search(raw)
    if header_match:
        raw = raw[header_match.end():]

    # strip footer
    footer_match = _FOOTER_START.search(raw)
    if footer_match:
        raw = raw[:footer_match.start()]

    # collapse excessive blank lines
    raw = re.sub(r'\n{4,}', '\n\n\n', raw)

    return raw.strip()


def get_summary(full_text, max_chars=500):
    """Extract first meaningful paragraph as summary."""
    paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
    for para in paragraphs:
        if len(para) > 80:
            return para[:max_chars]
    return full_text[:max_chars]


def make_unique_slug(title, existing_slugs):
    base_slug = slugify(title)[:490]
    slug = base_slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1
    existing_slugs.add(slug)
    return slug


# ============================================================
#  CATALOG READER
# ============================================================
def load_catalog():
    """
    Read pg_catalog.csv and return a dict keyed by book ID.
    """
    catalog = {}
    try:
        with open(META_PATH, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Type') == 'Text' and 'en' in row.get('Language', ''):
                    book_id = str(row['Text#']).strip()
                    catalog[book_id] = {
                        'title'   : row.get('Title', '').strip(),
                        'author'  : row.get('Authors', '').strip(),
                        'subjects': row.get('Subjects', '').strip(),
                    }
    except Exception as e:
        print(f"⚠️  Could not load catalog: {e}")
    return catalog


# ============================================================
#  PARSER
# ============================================================
def parse_books():
    print("=" * 60)
    print("  NET-1 Gutenberg Book Parser")
    print("=" * 60)
    print(f"  Books dir : {BOOKS_DIR}")
    print(f"  Batch size: {BATCH_SIZE}")
    print("=" * 60)

    # load catalog metadata
    catalog = load_catalog()
    print(f"\n  📚 Catalog entries: {len(catalog)}")

    # get list of downloaded book files
    book_files = [
        f for f in os.listdir(BOOKS_DIR)
        if f.startswith('pg') and f.endswith('.txt')
    ]
    print(f"  📂 Book files found: {len(book_files)}")

    # create source record
    source = Source.objects.create(
        name        = f"gutenberg-{datetime.now().strftime('%Y-%m')}",
        source_type = 'gutenberg',
        filename    = 'gutenberg/books/',
        notes       = f"Loaded on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"  ✅ Source record created: ID {source.id}\n")

    # track existing slugs
    existing_slugs = set(Document.objects.values_list('slug', flat=True))

    # counters
    total_new     = 0
    total_updated = 0
    total_skipped = 0
    total_failed  = 0

    new_batch      = []
    revision_batch = []

    for i, filename in enumerate(sorted(book_files), 1):
        try:
            # extract book ID from filename e.g. pg84.txt → 84
            book_id = filename.replace('pg', '').replace('.txt', '')

            # get metadata from catalog
            meta = catalog.get(book_id, {})
            title  = meta.get('title')  or f"Book {book_id}"
            author = meta.get('author') or None

            # clean author — Gutenberg format is "Lastname, Firstname, 1800-1900"
            if author:
                author = re.sub(r',?\s*\d{4}-\d{0,4}$', '', author).strip()

            subjects = meta.get('subjects', '')

            # read and clean book text
            filepath = os.path.join(BOOKS_DIR, filename)
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                raw = f.read()

            full_text = clean_book_text(raw)

            if len(full_text) < 100:
                print(f"  ⚠️  [{i:3d}] Skipping {filename} — too short after cleaning")
                total_skipped += 1
                continue

            summary = get_summary(full_text)

            # check if already exists
            existing_doc = Document.objects.filter(
                original_id = book_id,
                source_type = 'gutenberg'
            ).first()

            if existing_doc is None:
                # NEW BOOK
                slug = make_unique_slug(title, existing_slugs)
                new_batch.append(Document(
                    source_type  = 'gutenberg',
                    source       = source,
                    original_id  = book_id,
                    title        = title,
                    slug         = slug,
                    author       = author,
                    summary      = summary,
                    full_text    = full_text,
                    categories   = subjects,
                    language     = 'en',
                    last_updated = datetime.now(tz=timezone.utc),
                    is_active    = True,
                ))
                total_new += 1
                print(f"  ✅ [{i:3d}] {title[:60]}")

            elif existing_doc.full_text != full_text:
                # UPDATED BOOK
                existing_doc.source       = source
                existing_doc.summary      = summary
                existing_doc.full_text    = full_text
                existing_doc.categories   = subjects
                existing_doc.last_updated = datetime.now(tz=timezone.utc)
                existing_doc.save()

                last_revision = DocumentRevision.objects.filter(
                    document=existing_doc
                ).order_by('-version').first()

                revision_batch.append(DocumentRevision(
                    document = existing_doc,
                    source   = source,
                    version  = (last_revision.version + 1) if last_revision else 2,
                    diff     = '',
                    previous = last_revision,
                ))
                total_updated += 1
                print(f"  🔄 [{i:3d}] Updated: {title[:60]}")

            else:
                total_skipped += 1
                print(f"  ⏭️  [{i:3d}] Unchanged: {title[:60]}")

            # save batch
            if len(new_batch) >= BATCH_SIZE:
                Document.objects.bulk_create(new_batch, ignore_conflicts=True)
                slugs      = [d.slug for d in new_batch]
                saved_docs = Document.objects.filter(slug__in=slugs)
                for doc in saved_docs:
                    revision_batch.append(DocumentRevision(
                        document = doc,
                        source   = source,
                        version  = 1,
                        diff     = '',
                        previous = None,
                    ))
                new_batch = []

            if len(revision_batch) >= BATCH_SIZE:
                DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)
                revision_batch = []

        except Exception as e:
            print(f"  ❌ [{i:3d}] Failed {filename}: {e}")
            total_failed += 1

    # save remaining
    if new_batch:
        Document.objects.bulk_create(new_batch, ignore_conflicts=True)
        slugs      = [d.slug for d in new_batch]
        saved_docs = Document.objects.filter(slug__in=slugs)
        for doc in saved_docs:
            revision_batch.append(DocumentRevision(
                document = doc,
                source   = source,
                version  = 1,
                diff     = '',
                previous = None,
            ))

    if revision_batch:
        DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)

    # update source record
    source.total_documents = total_new + total_updated
    source.save()

    print("\n" + "=" * 60)
    print(f"  ✅ Parsing complete!")
    print(f"  New books     : {total_new}")
    print(f"  Updated       : {total_updated}")
    print(f"  Unchanged     : {total_skipped}")
    print(f"  Failed        : {total_failed}")
    print(f"  Source ID     : {source.id}")
    print("=" * 60)


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == '__main__':
    parse_books()