import os
import sys
import bz2
import difflib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re

# ============================================================
#  PATHS
# ============================================================
MAIN_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR  = os.path.dirname(MAIN_DIR)
DUMPS_DIR = os.path.join(BASE_DIR, 'data', 'dumps')

# Django setup
sys.path.append(MAIN_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.utils.text import slugify
from data_master.models import Source, Document, DocumentRevision
import mwparserfromhell

# ============================================================
#  CONFIG
# ============================================================
BATCH_SIZE   = 500
MAX_ARTICLES = None

# ============================================================
#  DUMP DETECTION
# ============================================================
def get_latest_dump(dumps_dir):
    files = [f for f in os.listdir(dumps_dir) if f.endswith('.xml.bz2')]
    if not files:
        raise FileNotFoundError(f"No dump files found in {dumps_dir}")
    if len(files) == 1:
        return os.path.join(dumps_dir, files[0])
    latest = max(files, key=lambda f: os.path.getmtime(os.path.join(dumps_dir, f)))
    print(f"  📂 Detected dump: {latest}")
    return os.path.join(dumps_dir, latest)

# ============================================================
#  NAMESPACE DETECTION
# ============================================================
def get_namespace(dump_path):
    with bz2.open(dump_path, 'rb') as f:
        for line in f:
            line = line.decode('utf-8', errors='ignore')
            if 'xmlns=' in line:
                start = line.find('xmlns="') + 7
                end   = line.find('"', start)
                ns    = line[start:end]
                return f'{{{ns}}}'
    raise ValueError("Could not detect XML namespace from dump file")

# ============================================================
#  HELPERS
# ============================================================
# compiled once at module level — much faster
_CLEANUP_PATTERNS = re.compile(
    r'(?m)^[ \t]*(?:'
    r'thumb\||thumbnail\||left\||right\||center\||centre\||'
    r'frame\||frameless\||upright[^\n]*|'
    r'(?:File|Image|file|image):[^\n]*'
    r')[^\n]*$\n?',
    re.IGNORECASE
)

def clean_text(raw_text):
    try:
        wikicode = mwparserfromhell.parse(raw_text)
        clean    = wikicode.strip_code().strip()
        clean    = _CLEANUP_PATTERNS.sub('', clean)
        # collapse 3+ blank lines into 2
        clean    = re.sub(r'\n{3,}', '\n\n', clean)
        return clean.strip()
    except Exception:
        return raw_text.strip()

def get_summary(full_text, max_chars=500):
    paragraphs = [p.strip() for p in full_text.split('\n') if p.strip()]
    for para in paragraphs:
        if len(para) > 50:
            return para[:max_chars]
    return full_text[:max_chars]

def get_categories(raw_text):
    categories = []
    try:
        wikicode = mwparserfromhell.parse(raw_text)
        for link in wikicode.filter_wikilinks():
            target = str(link.title)
            if target.startswith('Category:'):
                categories.append(target.replace('Category:', '').strip())
    except Exception:
        pass
    return ', '.join(categories)

def make_unique_slug(title, existing_slugs):
    base_slug = slugify(title)[:490]
    slug = base_slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1
    existing_slugs.add(slug)
    return slug

def compute_diff(old_text, new_text):
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile='previous', tofile='current', lineterm='')
    return ''.join(diff)

# ============================================================
#  PARSER
# ============================================================
def parse_dump(dump_path, max_articles=None):
    print("=" * 60)
    print("  NET-1 Wikipedia Dump Parser")
    print("=" * 60)
    print(f"  Dump file : {os.path.basename(dump_path)}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Max pages : {max_articles or 'unlimited'}")
    print("=" * 60)

    NS = get_namespace(dump_path)
    print(f"\n  📡 Namespace : {NS}")

    # create source record
    source = Source.objects.create(
        name        = os.path.basename(dump_path),
        source_type = 'wikipedia',
        filename    = os.path.basename(dump_path),
        notes       = f"Loaded on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"  ✅ Source record created: ID {source.id}")

    # track existing slugs
    existing_slugs = set(Document.objects.values_list('slug', flat=True))

    # counters
    total_parsed  = 0
    total_new     = 0
    total_updated = 0
    total_skipped = 0

    new_batch      = []
    revision_batch = []

    print("\n📖 Parsing dump file...\n")

    opener  = bz2.open(dump_path, 'rb')
    context = ET.iterparse(opener, events=('end',))

    for event, elem in context:
        if elem.tag == f'{NS}page':
            try:
                # skip non article pages
                ns = elem.find(f'{NS}ns')
                if ns is None or ns.text != '0':
                    elem.clear()
                    continue

                # get page id
                page_id_elem = elem.find(f'{NS}id')
                if page_id_elem is None:
                    elem.clear()
                    continue
                page_id = str(page_id_elem.text)

                # get title
                title_elem = elem.find(f'{NS}title')
                if title_elem is None:
                    elem.clear()
                    continue
                title = title_elem.text.strip()

                # skip redirects
                if elem.find(f'{NS}redirect') is not None:
                    elem.clear()
                    continue

                # get revision
                revision = elem.find(f'{NS}revision')
                if revision is None:
                    elem.clear()
                    continue

                text_elem = revision.find(f'{NS}text')
                if text_elem is None or not text_elem.text:
                    elem.clear()
                    continue

                raw_text = text_elem.text

                # get timestamp
                timestamp_elem = revision.find(f'{NS}timestamp')
                last_updated = None
                if timestamp_elem is not None:
                    try:
                        last_updated = datetime.strptime(
                            timestamp_elem.text, '%Y-%m-%dT%H:%M:%SZ'
                        ).replace(tzinfo=timezone.utc)
                    except Exception:
                        pass

                # clean and extract
                full_text  = clean_text(raw_text)
                summary    = get_summary(full_text)
                categories = get_categories(raw_text)

                # ── VERSION CONTROL LOGIC ──
                existing_doc = Document.objects.filter(
                    original_id   = page_id,
                    source_type = 'wikipedia'
                ).first()

                if existing_doc is None:
                    # BRAND NEW
                    slug = make_unique_slug(title, existing_slugs)
                    new_batch.append(Document(
                        source_type  = 'wikipedia',
                        source       = source,
                        original_id    = page_id,
                        title        = title,
                        slug         = slug,
                        summary      = summary,
                        full_text    = full_text,
                        categories   = categories,
                        language     = 'en',
                        last_updated = last_updated,
                        is_active    = True,
                    ))
                    total_new += 1

                elif existing_doc.full_text != full_text:
                    # CONTENT CHANGED
                    diff = compute_diff(existing_doc.full_text, full_text)

                    last_revision = DocumentRevision.objects.filter(
                        document=existing_doc
                    ).order_by('-version').first()

                    new_version = (last_revision.version + 1) if last_revision else 2

                    existing_doc.source       = source
                    existing_doc.summary      = summary
                    existing_doc.full_text    = full_text
                    existing_doc.categories   = categories
                    existing_doc.last_updated = last_updated
                    existing_doc.save()

                    revision_batch.append(DocumentRevision(
                        document = existing_doc,
                        source   = source,
                        version  = new_version,
                        diff     = diff,
                        previous = last_revision,
                    ))
                    total_updated += 1

                else:
                    # NO CHANGE
                    total_skipped += 1

                total_parsed += 1

                # save new batch
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
                    print(f"  ✅ New: {total_new} | Updated: {total_updated} | Skipped: {total_skipped}")

                # save revision batch
                if len(revision_batch) >= BATCH_SIZE:
                    DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)
                    revision_batch = []

                if max_articles and total_parsed >= max_articles:
                    break

            except Exception as e:
                print(f"  ⚠️  Error parsing page: {e}")
                total_skipped += 1
            finally:
                elem.clear()

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
    print(f"  Total parsed  : {total_parsed}")
    print(f"  New articles  : {total_new}")
    print(f"  Updated       : {total_updated}")
    print(f"  Unchanged     : {total_skipped}")
    print(f"  Source ID     : {source.id}")
    print("=" * 60)

# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == '__main__':
    dump_path = get_latest_dump(DUMPS_DIR)
    parse_dump(dump_path)