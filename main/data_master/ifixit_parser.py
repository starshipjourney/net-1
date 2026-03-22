import os
import sys
import json
import re
from datetime import datetime, timezone

# ============================================================
#  PATHS
# ============================================================
MAIN_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR   = os.path.dirname(MAIN_DIR)
IFIX_DIR   = os.path.join(BASE_DIR, 'data', 'dumps', 'ifixit')

# iFixit data dump structure:
#   data/dumps/ifixit/
#     guides/          ← JSON files, one per guide (guideid.json)
#     categories.json  ← optional category tree

sys.path.append(MAIN_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.utils.text import slugify
from data_master.models import Source, Document, DocumentRevision

# ============================================================
#  CONFIG
# ============================================================
BATCH_SIZE = 100

# ============================================================
#  TEXT EXTRACTION
# ============================================================
_HTML_TAG = re.compile(r'<[^>]+>')

def strip_html(text):
    """Remove HTML tags from iFixit step text."""
    if not text:
        return ''
    return _HTML_TAG.sub(' ', text).strip()


def extract_guide_text(guide_data):
    """
    Build full_text from iFixit guide JSON structure.
    Concatenates title, introduction, and all step text blocks.
    """
    parts = []

    # introduction
    intro = guide_data.get('introduction_rendered') or guide_data.get('introduction', '')
    if intro:
        parts.append(strip_html(intro))

    # steps
    for step in guide_data.get('steps', []):
        # step title
        step_title = step.get('title', '')
        if step_title:
            parts.append(f"\nStep {step.get('orderby', '')}: {step_title}")

        # step lines (each line has 'text_rendered' or 'text')
        for line in step.get('lines', []):
            text = line.get('text_rendered') or line.get('text', '')
            if text:
                parts.append(strip_html(text))

    # conclusion
    conclusion = guide_data.get('conclusion_rendered') or guide_data.get('conclusion', '')
    if conclusion:
        parts.append('\n' + strip_html(conclusion))

    return '\n'.join(parts).strip()


def get_summary(full_text, max_chars=500):
    paragraphs = [p.strip() for p in full_text.split('\n') if p.strip()]
    for para in paragraphs:
        if len(para) > 50:
            return para[:max_chars]
    return full_text[:max_chars]


def make_unique_slug(title, guide_id, existing_slugs):
    """Use ifix- prefix + guide ID for guaranteed uniqueness."""
    base_slug = f'ifix-{guide_id}-{slugify(title)}'[:490]
    slug      = base_slug
    counter   = 1
    while slug in existing_slugs:
        slug = f'{base_slug}-{counter}'
        counter += 1
    existing_slugs.add(slug)
    return slug


# ============================================================
#  PARSER
# ============================================================
def parse_guides(guides_dir=None):
    if guides_dir is None:
        guides_dir = os.path.join(IFIX_DIR, 'guides')

    print("=" * 60)
    print("  NET-1 iFixit Guide Parser")
    print("=" * 60)
    print(f"  Guides dir : {guides_dir}")
    print(f"  Batch size : {BATCH_SIZE}")
    print("=" * 60)

    if not os.path.isdir(guides_dir):
        print(f"  ❌ Guides directory not found: {guides_dir}")
        print(f"  Download iFixit dump and extract to {guides_dir}")
        return

    guide_files = [f for f in os.listdir(guides_dir) if f.endswith('.json')]
    print(f"\n  📂 Guide files found: {len(guide_files)}")

    # determine version from existing sources
    last_source  = Source.objects.filter(source_type='ifixit').order_by('-loaded_at').first()
    version_name = f"ifixit-{datetime.now().strftime('%Y-%m')}"

    source = Source.objects.create(
        name        = version_name,
        source_type = 'ifixit',
        filename    = 'ifixit/guides/',
        notes       = (
            f"Loaded on {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
            f"{'Re-import — checking for updated guides.' if last_source else 'Initial import.'}"
        )
    )
    print(f"  ✅ Source: {source.name} (ID {source.id})\n")

    existing_slugs = set(Document.objects.values_list('slug', flat=True))
    total_new      = 0
    total_updated  = 0
    total_skipped  = 0
    total_failed   = 0

    new_batch      = []
    revision_batch = []

    for i, filename in enumerate(sorted(guide_files), 1):
        filepath = os.path.join(guides_dir, filename)
        try:
            with open(filepath, encoding='utf-8') as f:
                guide = json.load(f)

            guide_id    = str(guide.get('guideid', filename.replace('.json', '')))
            title       = guide.get('title', f'Guide {guide_id}').strip()
            category    = guide.get('category', '')
            subject     = guide.get('subject', '')
            difficulty  = guide.get('difficulty', '')
            time_req    = guide.get('time_required', '')

            # categories string for our model
            cats_parts = [c for c in [category, subject, difficulty, time_req] if c]
            categories = ', '.join(cats_parts)

            full_text = extract_guide_text(guide)

            if len(full_text) < 50:
                print(f"  ⚠️  [{i:4d}] Skipping guide {guide_id} — too short")
                total_skipped += 1
                continue

            summary = get_summary(full_text)

            # parse last_updated from guide data
            last_updated = None
            modified_date = guide.get('modified_date')
            if modified_date:
                try:
                    last_updated = datetime.fromtimestamp(
                        int(modified_date), tz=timezone.utc
                    )
                except Exception:
                    pass

            existing_doc = Document.objects.filter(
                original_id = guide_id,
                source_type = 'ifixit'
            ).first()

            if existing_doc is None:
                slug = make_unique_slug(title, guide_id, existing_slugs)
                new_batch.append(Document(
                    source_type  = 'ifixit',
                    source       = source,
                    original_id  = guide_id,
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
                if i % 100 == 0:
                    print(f"  ✅ [{i:4d}] {title[:55]}")

            elif existing_doc.full_text != full_text:
                last_rev = DocumentRevision.objects.filter(
                    document=existing_doc
                ).order_by('-version').first()

                existing_doc.source       = source
                existing_doc.summary      = summary
                existing_doc.full_text    = full_text
                existing_doc.categories   = categories
                existing_doc.last_updated = last_updated
                existing_doc.save()

                revision_batch.append(DocumentRevision(
                    document = existing_doc,
                    source   = source,
                    version  = (last_rev.version + 1) if last_rev else 2,
                    diff     = '',  # diffs for prose guides are noisy — skip
                    previous = last_rev,
                ))
                total_updated += 1

            else:
                total_skipped += 1

            # flush batches
            if len(new_batch) >= BATCH_SIZE:
                Document.objects.bulk_create(new_batch, ignore_conflicts=True)
                for doc in Document.objects.filter(slug__in=[d.slug for d in new_batch]):
                    revision_batch.append(DocumentRevision(
                        document=doc, source=source, version=1, diff='', previous=None,
                    ))
                new_batch = []
                print(f"  ✅ New: {total_new} | Updated: {total_updated}")

            if len(revision_batch) >= BATCH_SIZE:
                DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)
                revision_batch = []

        except Exception as e:
            print(f"  ❌ [{i:4d}] Failed {filename}: {e}")
            total_failed += 1

    # flush remaining
    if new_batch:
        Document.objects.bulk_create(new_batch, ignore_conflicts=True)
        for doc in Document.objects.filter(slug__in=[d.slug for d in new_batch]):
            revision_batch.append(DocumentRevision(
                document=doc, source=source, version=1, diff='', previous=None,
            ))
    if revision_batch:
        DocumentRevision.objects.bulk_create(revision_batch, ignore_conflicts=True)

    source.total_documents = total_new + total_updated
    source.save()

    print("\n" + "=" * 60)
    print(f"  ✅ iFixit parse complete!")
    print(f"  New: {total_new} | Updated: {total_updated} | "
          f"Unchanged: {total_skipped} | Failed: {total_failed}")
    print(f"  Source: {source.name} (ID {source.id})")
    print("=" * 60)


if __name__ == '__main__':
    parse_guides()