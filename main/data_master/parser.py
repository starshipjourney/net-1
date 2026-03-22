import os
import sys
import bz2
import re
import difflib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ============================================================
#  PATHS
# ============================================================
MAIN_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR  = os.path.dirname(MAIN_DIR)
DUMPS_DIR = os.path.join(BASE_DIR, 'data', 'dumps', 'wikipedia')

sys.path.append(MAIN_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.utils.text import slugify
from data_master.models import Source, Document, DocumentRevision

# ============================================================
#  CONFIG
# ============================================================
BATCH_SIZE   = 2000   # larger = faster bulk inserts
REPORT_EVERY = 10000  # print progress every N articles

# ============================================================
#  FAST REGEX-BASED WIKI CLEANER
#  No mwparserfromhell — pure regex, ~20x faster
# ============================================================

# compiled once at module level
_RE_COMMENT    = re.compile(r'<!--.*?-->', re.DOTALL)
_RE_TAG        = re.compile(r'<[^>]+>', re.DOTALL)
_RE_TEMPLATE   = re.compile(r'\{\{[^{}]*\}\}')   # single-level templates
_RE_WIKILINK   = re.compile(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]')
_RE_EXTLINK    = re.compile(r'\[https?://[^\s\]]+(?:\s+([^\]]*))?\]')
_RE_HEADING    = re.compile(r'={2,}([^=]+)={2,}')
_RE_BOLD_IT    = re.compile(r"'{2,3}")
_RE_FILE       = re.compile(r'\[\[(?:File|Image|file|image):[^\]]*\]\]', re.IGNORECASE)
_RE_CATEGORY   = re.compile(r'\[\[Category:([^\]|]+)[^\]]*\]\]', re.IGNORECASE)
_RE_BLANK      = re.compile(r'\n{3,}')
_RE_SPACES     = re.compile(r'[ \t]+')
_RE_PIPE_TABLE = re.compile(r'^\s*[|!{].*$', re.MULTILINE)
_RE_MAGIC      = re.compile(r'__[A-Z_]+__')


def clean_wikitext(raw):
    """
    Fast regex-based wikitext cleaner.
    Strips markup and returns readable plain text.
    ~20x faster than mwparserfromhell on large dumps.
    """
    t = raw

    # remove HTML comments
    t = _RE_COMMENT.sub('', t)

    # remove file/image embeds
    t = _RE_FILE.sub('', t)

    # remove templates — loop to handle nested {{}}
    for _ in range(6):
        prev = t
        t    = _RE_TEMPLATE.sub('', t)
        if t == prev:
            break

    # convert wikilinks — keep display text
    t = _RE_WIKILINK.sub(r'\1', t)

    # convert external links — keep label if present
    t = _RE_EXTLINK.sub(lambda m: m.group(1) or '', t)

    # strip headings markers but keep text
    t = _RE_HEADING.sub(r'\n\1\n', t)

    # strip bold/italic markers
    t = _RE_BOLD_IT.sub('', t)

    # strip table syntax
    t = _RE_PIPE_TABLE.sub('', t)

    # strip magic words
    t = _RE_MAGIC.sub('', t)

    # strip remaining HTML tags
    t = _RE_TAG.sub('', t)

    # collapse whitespace
    t = _RE_SPACES.sub(' ', t)
    t = _RE_BLANK.sub('\n\n', t)

    return t.strip()


def extract_categories(raw):
    """Extract category names from raw wikitext."""
    cats = _RE_CATEGORY.findall(raw)
    return ', '.join(c.strip() for c in cats)


def get_summary(full_text, max_chars=500):
    """First substantial paragraph as summary."""
    for para in full_text.split('\n'):
        para = para.strip()
        if len(para) > 80:
            return para[:max_chars]
    return full_text[:max_chars]


def make_slug(source_type, page_id, title):
    prefix     = source_type[:4]
    title_part = slugify(title)[:200]
    return f'{prefix}-{page_id}-{title_part}'


def compute_diff(old, new):
    return ''.join(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile='previous', tofile='current', lineterm=''
    ))


def get_namespace(dump_path):
    with bz2.open(dump_path, 'rb') as f:
        for line in f:
            line = line.decode('utf-8', errors='ignore')
            if 'xmlns=' in line:
                start = line.find('xmlns="') + 7
                end   = line.find('"', start)
                return f'{{{line[start:end]}}}'
    raise ValueError("Could not detect XML namespace")


def get_latest_dump(dumps_dir):
    files = [f for f in os.listdir(dumps_dir) if f.endswith('.xml.bz2')]
    if not files:
        raise FileNotFoundError(f"No dump files found in {dumps_dir}")
    return os.path.join(dumps_dir, max(
        files, key=lambda f: os.path.getmtime(os.path.join(dumps_dir, f))
    ))


# ============================================================
#  PARSER
# ============================================================
def parse_dump(dump_path, source_type='wikipedia', max_articles=None):
    print("=" * 60)
    print(f"  NET-1 {source_type.title()} Dump Parser  [FAST MODE]")
    print("=" * 60)
    print(f"  Dump      : {os.path.basename(dump_path)}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Max pages : {max_articles or 'unlimited'}")
    print(f"  Mode      : pure-regex (no mwparserfromhell)")
    print("=" * 60)

    NS   = get_namespace(dump_path)
    fname = os.path.basename(dump_path)
    tag   = fname.split('-')[1] if '-' in fname else 'latest'

    source = Source.objects.create(
        name        = f'{source_type}-{tag}',
        source_type = source_type,
        filename    = fname,
        notes       = f"Fast-parsed on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"\n  ✅ Source: {source.name} (ID {source.id})")
    print(f"\n  📖 Parsing...\n")

    t_start        = datetime.now()
    total_parsed  = 0
    total_new     = 0
    total_updated = 0
    total_skipped = 0

    new_batch      = []
    revision_batch = []

    # pre-load existing original_ids for this source_type for fast lookup
    existing_ids = set(
        Document.objects.filter(source_type=source_type)
        .values_list('original_id', flat=True)
    )

    opener  = bz2.open(dump_path, 'rb')
    context = ET.iterparse(opener, events=('end',))

    for event, elem in context:
        if elem.tag != f'{NS}page':
            continue

        try:
            # main namespace only
            ns_elem = elem.find(f'{NS}ns')
            if ns_elem is None or ns_elem.text != '0':
                elem.clear()
                continue

            # skip redirects
            if elem.find(f'{NS}redirect') is not None:
                elem.clear()
                continue

            page_id_elem = elem.find(f'{NS}id')
            title_elem   = elem.find(f'{NS}title')
            if page_id_elem is None or title_elem is None:
                elem.clear()
                continue

            page_id = str(page_id_elem.text)
            title   = title_elem.text.strip()

            revision = elem.find(f'{NS}revision')
            if revision is None:
                elem.clear()
                continue

            text_elem = revision.find(f'{NS}text')
            if text_elem is None or not text_elem.text:
                elem.clear()
                continue

            raw_text = text_elem.text

            # skip very short stubs
            if len(raw_text) < 100:
                elem.clear()
                continue

            # timestamp
            last_updated = None
            ts_elem = revision.find(f'{NS}timestamp')
            if ts_elem is not None:
                try:
                    last_updated = datetime.strptime(
                        ts_elem.text, '%Y-%m-%dT%H:%M:%SZ'
                    ).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            # ── fast clean ──
            categories = extract_categories(raw_text)
            full_text  = clean_wikitext(raw_text)
            summary    = get_summary(full_text)

            # skip if cleaning left almost nothing
            if len(full_text) < 50:
                elem.clear()
                continue

            # ── version control ──
            if page_id not in existing_ids:
                # NEW
                slug = make_slug(source_type, page_id, title)
                new_batch.append(Document(
                    source_type  = source_type,
                    source       = source,
                    original_id  = page_id,
                    title        = title,
                    slug         = slug,
                    summary      = summary,
                    full_text    = full_text,
                    categories   = categories,
                    language     = 'en',
                    last_updated = last_updated,
                    is_active    = True,
                ))
                existing_ids.add(page_id)
                total_new += 1

            else:
                # POSSIBLE UPDATE — only load if needed
                existing_doc = Document.objects.filter(
                    original_id = page_id,
                    source_type = source_type
                ).only('id', 'full_text', 'slug').first()

                if existing_doc and existing_doc.full_text != full_text:
                    last_rev = DocumentRevision.objects.filter(
                        document=existing_doc
                    ).order_by('-version').values('id', 'version').first()

                    existing_doc.source       = source
                    existing_doc.summary      = summary
                    existing_doc.full_text    = full_text
                    existing_doc.categories   = categories
                    existing_doc.last_updated = last_updated
                    existing_doc.save()

                    revision_batch.append(DocumentRevision(
                        document  = existing_doc,
                        source    = source,
                        version   = (last_rev['version'] + 1) if last_rev else 2,
                        diff      = compute_diff(existing_doc.full_text or '', full_text),
                        previous_id = last_rev['id'] if last_rev else None,
                    ))
                    total_updated += 1
                else:
                    total_skipped += 1

            total_parsed += 1

            # ── flush new batch ──
            if len(new_batch) >= BATCH_SIZE:
                Document.objects.bulk_create(new_batch, ignore_conflicts=True)
                for doc in Document.objects.filter(
                    slug__in=[d.slug for d in new_batch]
                ).only('id', 'slug'):
                    revision_batch.append(DocumentRevision(
                        document=doc, source=source,
                        version=1, diff='', previous=None,
                    ))
                new_batch = []

            if len(revision_batch) >= BATCH_SIZE:
                DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)
                revision_batch = []

            # ── progress report ──
            if total_parsed % REPORT_EVERY == 0:
                elapsed = (datetime.now() - t_start).seconds
                rate    = total_parsed // max(elapsed, 1)
                print(
                    f"  📖 {total_parsed:>8,} parsed | "
                    f"{total_new:>7,} new | "
                    f"{total_updated:>5,} updated | "
                    f"{rate:>4,}/s"
                )

            if max_articles and total_parsed >= max_articles:
                break

        except Exception as e:
            total_skipped += 1
        finally:
            elem.clear()

    # ── flush remaining ──
    if new_batch:
        Document.objects.bulk_create(new_batch, ignore_conflicts=True)
        for doc in Document.objects.filter(
            slug__in=[d.slug for d in new_batch]
        ).only('id', 'slug'):
            revision_batch.append(DocumentRevision(
                document=doc, source=source,
                version=1, diff='', previous=None,
            ))

    if revision_batch:
        DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)

    source.total_documents = total_new + total_updated
    source.save()

    elapsed = (datetime.now() - t_start).seconds
    rate    = total_parsed // max(elapsed, 1)

    print("\n" + "=" * 60)
    print(f"  ✅ Parse complete!")
    print(f"  Total parsed  : {total_parsed:,}")
    print(f"  New           : {total_new:,}")
    print(f"  Updated       : {total_updated:,}")
    print(f"  Unchanged     : {total_skipped:,}")
    print(f"  Time          : {elapsed}s  ({rate}/s avg)")
    print(f"  Source        : {source.name} (ID {source.id})")
    print("=" * 60)


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == '__main__':
    dump_path = get_latest_dump(DUMPS_DIR)
    parse_dump(dump_path, source_type='wikipedia')