#!/usr/bin/env python3
"""
NET-1 Data Downloader
=====================
Downloads latest data for all configured sources into data/dumps/.

Usage:
    python3 download_data.py                        # download all sources, full data
    python3 download_data.py --sources wiki books   # specific sources only
    python3 download_data.py --sample               # sample/test mode (small datasets)
    python3 download_data.py --limit 500            # limit records per source
    python3 download_data.py --sources arxiv --limit 10000

Available source keys:
    wiki        Wikipedia English dump
    wikibooks   Wikibooks English dump
    wikivoyage  Wikivoyage English dump
    gutenberg   Project Gutenberg books
    ifixit      iFixit repair guides (via API)
    arxiv       arXiv abstracts (via Kaggle)

Sample mode limits:
    wiki        → 50 MB stub dump (first 50k articles)
    wikibooks   → full dump (~300 MB — already small)
    wikivoyage  → full dump (~150 MB — already small)
    gutenberg   → top 100 most downloaded books
    ifixit      → first 200 guides
    arxiv       → 50,000 records from snapshot
"""

import os
import sys
import time
import json
import shutil
import hashlib
import argparse
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path

# ============================================================
#  PATHS
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR   = SCRIPT_DIR.parent   # net-1/
DUMPS_DIR  = BASE_DIR / 'data' / 'dumps'

# ============================================================
#  REQUEST HELPERS
# ============================================================
DEFAULT_HEADERS = {
    'User-Agent': 'NET-1/1.0 offline-knowledge-system (non-commercial)',
}

def http_get(url, headers=None, timeout=60):
    """Simple HTTP GET, returns response object."""
    req_headers = {**DEFAULT_HEADERS, **(headers or {})}
    req = urllib.request.Request(url, headers=req_headers)
    return urllib.request.urlopen(req, timeout=timeout)


def download_file(url, dest_path, label='', resume=True):
    """
    Download url to dest_path with progress reporting.
    Supports byte-range resume if file partially exists.
    Returns True on success.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    existing_size = dest_path.stat().st_size if dest_path.exists() and resume else 0

    headers = {}
    if existing_size:
        headers['Range'] = f'bytes={existing_size}-'
        print(f"  ↪ Resuming {label} from {_fmt_bytes(existing_size)}...")
    else:
        print(f"  ⬇  Downloading {label}...")

    try:
        response = http_get(url, headers=headers)
        total    = int(response.headers.get('Content-Length', 0))
        total   += existing_size

        mode     = 'ab' if existing_size else 'wb'
        written  = existing_size
        chunk    = 1024 * 512   # 512 KB chunks

        with open(dest_path, mode) as f:
            while True:
                data = response.read(chunk)
                if not data:
                    break
                f.write(data)
                written += len(data)
                if total:
                    pct = written / total * 100
                    print(
                        f"\r     {_fmt_bytes(written)} / {_fmt_bytes(total)} "
                        f"({pct:.1f}%)",
                        end='', flush=True
                    )
        print()
        print(f"  ✅ Saved to {dest_path.name}")
        return True

    except urllib.error.HTTPError as e:
        if e.code == 416 and existing_size:
            # Range Not Satisfiable — file already complete
            print(f"  ✅ Already complete: {dest_path.name}")
            return True
        print(f"  ❌ HTTP {e.code}: {e.reason}")
        return False

    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


def _fmt_bytes(n):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


# ============================================================
#  WIKIPEDIA
# ============================================================
def download_wikipedia(sample=False, limit=None):
    """
    Full dump:   ~25 GB compressed   (enwiki articles XML)
    Sample mode: ~50 MB              (simplewiki — smaller but same format)
    """
    print("\n" + "=" * 60)
    print("  WIKIPEDIA")
    print("=" * 60)

    if sample:
        # Simple English Wikipedia — same format, vastly smaller (~50 MB)
        url  = "https://dumps.wikimedia.org/simplewiki/latest/simplewiki-latest-pages-articles.xml.bz2"
        dest = DUMPS_DIR / 'wikipedia' / 'simplewiki-latest-pages-articles.xml.bz2'
        print("  ℹ  Sample mode: downloading Simple English Wikipedia (~50 MB)")
    else:
        url  = "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2"
        dest = DUMPS_DIR / 'wikipedia' / 'enwiki-latest-pages-articles.xml.bz2'
        print("  ℹ  Full mode: downloading English Wikipedia (~25 GB compressed)")
        print("  ⚠️  This will take a long time. Ctrl+C to pause — download resumes automatically.")

    return download_file(url, dest, label='Wikipedia dump')


# ============================================================
#  WIKIBOOKS
# ============================================================
def download_wikibooks(sample=False, limit=None):
    """
    Full dump: ~300 MB compressed.
    No sample mode needed — it's already small.
    """
    print("\n" + "=" * 60)
    print("  WIKIBOOKS")
    print("=" * 60)

    url  = "https://dumps.wikimedia.org/enwikibooks/latest/enwikibooks-latest-pages-articles.xml.bz2"
    dest = DUMPS_DIR / 'wikibooks' / 'enwikibooks-latest-pages-articles.xml.bz2'

    if sample:
        print("  ℹ  Wikibooks is already small (~300 MB) — downloading full dump.")

    return download_file(url, dest, label='Wikibooks dump')


# ============================================================
#  WIKIVOYAGE
# ============================================================
def download_wikivoyage(sample=False, limit=None):
    """
    Full dump: ~150 MB compressed.
    No sample mode needed — it's already small.
    """
    print("\n" + "=" * 60)
    print("  WIKIVOYAGE")
    print("=" * 60)

    url  = "https://dumps.wikimedia.org/enwikivoyage/latest/enwikivoyage-latest-pages-articles.xml.bz2"
    dest = DUMPS_DIR / 'wikivoyage' / 'enwikivoyage-latest-pages-articles.xml.bz2'

    if sample:
        print("  ℹ  Wikivoyage is already small (~150 MB) — downloading full dump.")

    return download_file(url, dest, label='Wikivoyage dump')


# ============================================================
#  PROJECT GUTENBERG
# ============================================================
def download_gutenberg(sample=False, limit=None):
    """
    Downloads:
      1. pg_catalog.csv  — metadata for all 70k books (~14 MB)
      2. Individual .txt files for each book

    Sample mode: top 100 most downloaded books
    Full mode:   all English plain-text books (~40,000, ~12 GB)
    Limit:       download only N books (overrides sample)
    """
    print("\n" + "=" * 60)
    print("  PROJECT GUTENBERG")
    print("=" * 60)

    books_dir  = DUMPS_DIR / 'gutenberg' / 'books'
    meta_path  = DUMPS_DIR / 'gutenberg' / 'pg_catalog.csv'
    books_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: catalog ──
    print("\n  Step 1/2: Downloading catalog...")
    catalog_ok = download_file(
        'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv',
        meta_path,
        label='Gutenberg catalog'
    )
    if not catalog_ok:
        return False

    # ── Step 2: parse catalog for English text books ──
    import csv
    book_ids = []
    with open(meta_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Type') == 'Text' and 'en' in row.get('Language', ''):
                book_ids.append(row['Text#'].strip())

    print(f"\n  📚 Found {len(book_ids):,} English text books in catalog")

    # apply limits
    if limit:
        book_ids = book_ids[:limit]
        print(f"  ℹ  Limit applied: downloading {limit} books")
    elif sample:
        book_ids = book_ids[:100]
        print(f"  ℹ  Sample mode: downloading top 100 books")
    else:
        print(f"  ℹ  Full mode: downloading all {len(book_ids):,} books")
        print(f"  ⚠️  This requires ~12 GB and several hours.")

    # ── Step 3: download books ──
    print(f"\n  Step 2/2: Downloading book files...")
    downloaded = 0
    skipped    = 0
    failed     = 0

    for i, book_id in enumerate(book_ids, 1):
        dest = books_dir / f'pg{book_id}.txt'

        if dest.exists() and dest.stat().st_size > 100:
            skipped += 1
            if i % 500 == 0:
                print(f"  ⏭  [{i:5d}/{len(book_ids)}] Skipped (exists): {book_id}")
            continue

        # Gutenberg URL format
        url = f'https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt'

        try:
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()

            with open(dest, 'wb') as f:
                f.write(content)

            downloaded += 1
            if i % 50 == 0 or i <= 10:
                print(f"  ✅ [{i:5d}/{len(book_ids)}] Book {book_id} — {_fmt_bytes(len(content))}")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # try alternate URL format
                alt_url = f'https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt'
                try:
                    req = urllib.request.Request(alt_url, headers=DEFAULT_HEADERS)
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        content = resp.read()
                    with open(dest, 'wb') as f:
                        f.write(content)
                    downloaded += 1
                    continue
                except Exception:
                    pass
            failed += 1
            if i % 100 == 0:
                print(f"  ❌ [{i:5d}] Book {book_id} not available")

        except Exception as e:
            failed += 1

        # polite delay — Gutenberg asks for this
        time.sleep(0.5)

    print(f"\n  ✅ Gutenberg complete: {downloaded} downloaded, "
          f"{skipped} skipped, {failed} failed")
    return True


# ============================================================
#  iFixit
# ============================================================
def download_ifixit(sample=False, limit=None):
    """
    Downloads guides from the iFixit public API as JSON files.
    Sample mode: 200 guides
    Full mode:   all ~44,000 English guides
    Limit:       download N guides
    """
    print("\n" + "=" * 60)
    print("  iFIXIT")
    print("=" * 60)

    guides_dir = DUMPS_DIR / 'ifixit' / 'guides'
    guides_dir.mkdir(parents=True, exist_ok=True)

    BASE_API    = 'https://www.ifixit.com/api/2.0'
    BATCH       = 20
    DELAY       = 1.0   # seconds between requests

    max_guides = limit or (200 if sample else None)

    if sample:
        print(f"  ℹ  Sample mode: downloading {max_guides} guides")
    elif limit:
        print(f"  ℹ  Limit: {limit} guides")
    else:
        print(f"  ℹ  Full mode: downloading all English guides (~44,000)")
        print(f"  ⚠️  Estimated time: 12-15 hours at polite rate.")

    downloaded = 0
    skipped    = 0
    failed     = 0
    offset     = 0

    while True:
        listing_url = f'{BASE_API}/guides?order=id&limit={BATCH}&offset={offset}&langid=en'

        try:
            with http_get(listing_url) as resp:
                listing = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"  ❌ Failed to fetch listing at offset {offset}: {e}")
            break

        if not listing or not isinstance(listing, list):
            print(f"  📭 No more guides at offset {offset}.")
            break

        for guide_summary in listing:
            guide_id = guide_summary.get('guideid')
            if not guide_id:
                continue

            dest = guides_dir / f'{guide_id}.json'

            if dest.exists():
                skipped += 1
            else:
                try:
                    detail_url = f'{BASE_API}/guides/{guide_id}'
                    with http_get(detail_url) as resp:
                        data = json.loads(resp.read().decode('utf-8'))

                    with open(dest, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    downloaded += 1
                    if downloaded % 100 == 0:
                        print(f"  ✅ Downloaded: {downloaded:,} | "
                              f"Skipped: {skipped:,} | Failed: {failed:,}")

                except Exception as e:
                    failed += 1

                time.sleep(DELAY)

            total_seen = downloaded + skipped
            if max_guides and total_seen >= max_guides:
                break

        total_seen = downloaded + skipped
        if max_guides and total_seen >= max_guides:
            print(f"  🛑 Reached limit of {max_guides} guides.")
            break

        offset += BATCH
        time.sleep(DELAY)

    print(f"\n  ✅ iFixit complete: {downloaded} downloaded, "
          f"{skipped} skipped, {failed} failed")
    return True


# ============================================================
#  arXiv
# ============================================================
def download_arxiv(sample=False, limit=None):
    """
    Downloads arXiv paper metadata directly from arXiv's OAI-PMH API.
    No account or API key required.

    arXiv OAI-PMH endpoint: https://export.arxiv.org/oai2
    Returns metadata in XML — we extract title, authors, abstract, categories.
    Output: line-delimited JSON matching the format arxiv_parser.py expects.

    Full corpus:  ~2.4M papers, 4 GB — takes several hours (polite rate limiting)
    Sample mode:  2,000 records — completes in ~5 minutes
    Limit N:      stops after N records
    """
    print("\n" + "=" * 60)
    print("  arXiv ABSTRACTS  (via OAI-PMH — no account needed)")
    print("=" * 60)

    arxiv_dir = DUMPS_DIR / 'arxiv'
    arxiv_dir.mkdir(parents=True, exist_ok=True)

    out_path = arxiv_dir / 'arxiv-metadata-oai-snapshot.json'

    max_records = limit or (2_000 if sample else None)

    if sample:
        print(f"  ℹ  Sample mode: fetching {max_records:,} records")
    elif limit:
        print(f"  ℹ  Limit: {limit:,} records")
    else:
        print(f"  ℹ  Full mode: fetching all ~2.4M records")
        print(f"  ⚠️  This will take many hours. Ctrl+C to pause — resumable.")

    # ── Resume support: count existing records ──
    existing = 0
    resumption_token = None

    if out_path.exists():
        with open(out_path, encoding='utf-8') as f:
            existing = sum(1 for line in f if line.strip())
        print(f"  ↪ Resuming — {existing:,} records already saved")

        # Load saved resumption token if it exists
        token_path = arxiv_dir / '.oai_resumption_token'
        if token_path.exists():
            resumption_token = token_path.read_text().strip() or None
            if resumption_token:
                print(f"  ↪ Using saved resumption token")

    # ── OAI-PMH harvesting ──
    OAI_BASE   = 'https://export.arxiv.org/oai2'
    OAI_DELAY  = 20   # arXiv asks for 20s between requests — mandatory
    NS         = {
        'oai':  'http://www.openarchives.org/OAI/2.0/',
        'dc':   'http://purl.org/dc/elements/1.1/',
        'oai_dc': 'http://www.openarchives.org/OAI/2.0/oai_dc/',
    }

    import xml.etree.ElementTree as ET

    total_fetched = existing
    total_written = 0
    page_num      = 0

    write_mode = 'a' if existing else 'w'

    try:
        with open(out_path, write_mode, encoding='utf-8') as out_f:

            while True:
                # build URL
                if resumption_token:
                    url = (f"{OAI_BASE}?verb=ListRecords"
                           f"&resumptionToken={urllib.parse.quote(resumption_token)}")
                else:
                    url = (f"{OAI_BASE}?verb=ListRecords"
                           f"&metadataPrefix=oai_dc"
                           f"&set=cs")   # start with cs — remove for all subjects

                page_num += 1

                try:
                    with http_get(url, timeout=60) as resp:
                        xml_data = resp.read()
                except Exception as e:
                    print(f"\n  ❌ Request failed: {e}. Retrying in 30s...")
                    time.sleep(30)
                    continue

                try:
                    root = ET.fromstring(xml_data)
                except ET.ParseError as e:
                    print(f"\n  ❌ XML parse error: {e}. Skipping page.")
                    time.sleep(OAI_DELAY)
                    continue

                # extract records
                records = root.findall('.//oai:record', NS)

                for record in records:
                    try:
                        # header
                        header    = record.find('oai:header', NS)
                        if header is None:
                            continue

                        status = header.get('status', '')
                        if status == 'deleted':
                            continue

                        identifier = header.findtext('oai:identifier', '', NS)
                        # identifier like: oai:arXiv.org:2103.01234
                        arxiv_id   = identifier.replace('oai:arXiv.org:', '').strip()

                        datestamp  = header.findtext('oai:datestamp', '', NS)

                        # metadata
                        metadata = record.find('.//oai_dc:dc', NS)
                        if metadata is None:
                            continue

                        title    = (metadata.findtext('dc:title', '', NS) or '').strip()
                        abstract = (metadata.findtext('dc:description', '', NS) or '').strip()
                        creators = metadata.findall('dc:creator', NS)
                        subjects = metadata.findall('dc:subject', NS)

                        if not title or not abstract:
                            continue

                        # format authors as list of [last, first, ''] lists
                        authors_parsed = []
                        for creator in creators:
                            name = (creator.text or '').strip()
                            if ',' in name:
                                parts = [p.strip() for p in name.split(',', 1)]
                                authors_parsed.append([parts[0], parts[1], ''])
                            else:
                                authors_parsed.append([name, '', ''])

                        # categories from dc:subject
                        cats = ' '.join(
                            s.text.strip() for s in subjects if s.text
                        )

                        # write as JSON line — matches arxiv_parser.py format
                        record_dict = {
                            'id':             arxiv_id,
                            'title':          title,
                            'abstract':       abstract,
                            'authors_parsed': authors_parsed,
                            'categories':     cats,
                            'update_date':    datestamp,
                        }
                        out_f.write(json.dumps(record_dict) + '\n')
                        total_written += 1
                        total_fetched += 1

                    except Exception:
                        continue

                out_f.flush()

                if page_num % 5 == 0 or page_num == 1:
                    print(f"  📖 Page {page_num} | "
                          f"Total: {total_fetched:,} records | "
                          f"This run: {total_written:,}")

                # check limit
                if max_records and total_fetched >= max_records:
                    print(f"\n  🛑 Reached limit of {max_records:,} records.")
                    break

                # get resumption token for next page
                token_elem = root.find('.//oai:resumptionToken', NS)
                if token_elem is None or not token_elem.text:
                    print(f"\n  📭 Harvest complete — no more pages.")
                    # clear saved token
                    token_path = arxiv_dir / '.oai_resumption_token'
                    if token_path.exists():
                        token_path.unlink()
                    break

                resumption_token = token_elem.text.strip()

                # save token so we can resume if interrupted
                (arxiv_dir / '.oai_resumption_token').write_text(resumption_token)

                # mandatory delay — arXiv OAI requires 20s between requests
                time.sleep(OAI_DELAY)

    except KeyboardInterrupt:
        print(f"\n  ⚠️  Interrupted. Progress saved — re-run to continue.")
        return True

    print(f"\n  ✅ arXiv complete: {total_fetched:,} total records in {out_path.name}")
    return True






# ============================================================
#  SOURCE REGISTRY
# ============================================================
SOURCES = {
    'wiki':       {'fn': download_wikipedia,  'desc': 'English Wikipedia (~25 GB compressed)'},
    'wikibooks':  {'fn': download_wikibooks,  'desc': 'English Wikibooks (~300 MB)'},
    'wikivoyage': {'fn': download_wikivoyage, 'desc': 'English Wikivoyage (~150 MB)'},
    'gutenberg':  {'fn': download_gutenberg,  'desc': 'Project Gutenberg books (~12 GB full)'},
    'ifixit':     {'fn': download_ifixit,     'desc': 'iFixit repair guides (~44k guides)'},
    'arxiv':      {'fn': download_arxiv,      'desc': 'arXiv abstracts (~4 GB)'},
}

# ============================================================
#  MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='NET-1 Data Downloader — downloads all knowledge sources.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--sources', '-s',
        nargs='+',
        choices=list(SOURCES.keys()),
        default=list(SOURCES.keys()),
        metavar='SOURCE',
        help=(
            f"Which sources to download. "
            f"Options: {', '.join(SOURCES.keys())}. "
            f"Default: all sources."
        )
    )

    parser.add_argument(
        '--sample',
        action='store_true',
        help=(
            'Download small sample datasets for testing. '
            'Wiki→simplewiki, Gutenberg→100 books, iFixit→200 guides, '
            'arXiv→50k records.'
        )
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        metavar='N',
        help=(
            'Limit the number of records/files downloaded per source. '
            'Applies to Gutenberg (books), iFixit (guides), and arXiv (records). '
            'Overrides --sample limits.'
        )
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List available sources and exit.'
    )

    args = parser.parse_args()

    if args.list:
        print("\nAvailable sources:")
        for key, info in SOURCES.items():
            print(f"  {key:<12}  {info['desc']}")
        print()
        return

    print("=" * 60)
    print("  NET-1 Data Downloader")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"  Sources : {', '.join(args.sources)}")
    print(f"  Sample  : {args.sample}")
    print(f"  Limit   : {args.limit or 'none'}")
    print(f"  Output  : {DUMPS_DIR}")
    print("=" * 60)

    DUMPS_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    for key in args.sources:
        fn = SOURCES[key]['fn']
        try:
            ok = fn(sample=args.sample, limit=args.limit)
            results[key] = '✅ OK' if ok else '❌ FAILED'
        except KeyboardInterrupt:
            print(f"\n  ⚠️  Interrupted during {key}.")
            results[key] = '⚠️  INTERRUPTED'
            break
        except Exception as e:
            print(f"  ❌ {key} failed with unexpected error: {e}")
            results[key] = f'❌ ERROR: {e}'

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for key, status in results.items():
        print(f"  {key:<12}  {status}")
    print()
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n  Next step — run parsers to load data into PostgreSQL:")
    for key in results:
        parser_map = {
            'wiki':       'python3 data_master/parser.py',
            'wikibooks':  'python3 data_master/wikibooks_parser.py',
            'wikivoyage': 'python3 data_master/wikivoyage_parser.py',
            'gutenberg':  'python3 data_master/gutenberg_parser.py',
            'ifixit':     'python3 data_master/ifixit_parser.py',
            'arxiv':      'python3 data_master/arxiv_parser.py',
        }
        if key in parser_map and '✅' in results.get(key, ''):
            print(f"  {parser_map[key]}")
    print()


if __name__ == '__main__':
    main()