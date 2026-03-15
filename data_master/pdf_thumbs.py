"""
NET-1 PDF Thumbnail Generator
==============================
Generates first-page thumbnails for PDFs in data/pdfs/.
Uses Valkey to track which files have been processed.
Thumbnails saved to data/pdf_thumbs/ as WebP images.

Run manually:
    python3 data_master/pdf_thumbs.py

Or call generate_thumbnail(pdf_path) from views for on-demand generation.
"""

import os
import sys
import time
import hashlib
from pathlib import Path

# Django setup
MAIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR  = os.path.dirname(MAIN_DIR)

sys.path.append(MAIN_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.conf import settings

# ============================================================
#  PATHS — read from settings so they work in containers too
# ============================================================
PDF_DIR   = Path(getattr(settings, 'PDF_DIR',   Path(BASE_DIR) / 'data' / 'pdfs'))
THUMB_DIR = Path(getattr(settings, 'THUMB_DIR', Path(BASE_DIR) / 'data' / 'pdf_thumbs'))
THUMB_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
#  VALKEY  (Redis-compatible)
# ============================================================
try:
    import redis
    _vk = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    _vk.ping()
    VALKEY_OK = True
    print("  ✅ Valkey connected")
except Exception as e:
    _vk      = None
    VALKEY_OK = False
    print(f"  ⚠️  Valkey unavailable: {e} — running without cache")

CACHE_PREFIX = 'net1:pdf_thumb:'
CACHE_TTL    = 60 * 60 * 24 * 30   # 30 days — thumbnails don't expire often


def _cache_key(pdf_path):
    """Stable key based on filename + file size (detects file replacement)."""
    p     = Path(pdf_path)
    fsize = p.stat().st_size if p.exists() else 0
    raw   = f"{p.name}:{fsize}"
    return CACHE_PREFIX + hashlib.md5(raw.encode()).hexdigest()


def _thumb_path(pdf_path):
    """Return the thumbnail path for a given PDF."""
    p    = Path(pdf_path)
    stem = hashlib.md5(p.name.encode()).hexdigest()[:16]
    return THUMB_DIR / f"{stem}.webp"


def is_cached(pdf_path):
    """Return True if this PDF's thumbnail is already generated and cached."""
    thumb = _thumb_path(pdf_path)
    if not thumb.exists():
        return False
    if _vk:
        return bool(_vk.get(_cache_key(pdf_path)))
    return True   # no Valkey — just check file exists


def generate_thumbnail(pdf_path, size=(180, 240)):
    """
    Generate a WebP thumbnail from page 1 of a PDF.
    Returns Path to thumbnail on success, None on failure.
    Skips if already cached.
    """
    pdf_path = Path(pdf_path)
    thumb    = _thumb_path(pdf_path)

    # already done
    if is_cached(pdf_path):
        return thumb

    # lock via Valkey to prevent concurrent generation of same file
    lock_key = _cache_key(pdf_path) + ':lock'
    if _vk:
        acquired = _vk.set(lock_key, '1', nx=True, ex=30)
        if not acquired:
            # another process is generating — wait briefly then return existing
            time.sleep(1)
            return thumb if thumb.exists() else None

    try:
        from pdf2image import convert_from_path
        from PIL import Image

        pages = convert_from_path(
            str(pdf_path),
            first_page = 1,
            last_page  = 1,
            dpi        = 96,
            size       = size,
        )

        if not pages:
            return None

        img = pages[0]

        # crop to exact size maintaining aspect ratio
        img.thumbnail(size, Image.LANCZOS)

        # save as WebP (small file size, good quality)
        img.save(str(thumb), 'WEBP', quality=75, method=4)

        # cache the result
        if _vk:
            _vk.set(_cache_key(pdf_path), '1', ex=CACHE_TTL)

        return thumb

    except ImportError:
        print("  ❌ pdf2image or Pillow not installed")
        print("     Run: sudo apt install poppler-utils -y")
        print("          pip install pdf2image Pillow --break-system-packages")
        return None

    except Exception as e:
        print(f"  ❌ Failed to generate thumbnail for {pdf_path.name}: {e}")
        return None

    finally:
        if _vk:
            _vk.delete(lock_key)


def get_thumbnail_url(pdf_relative_path):
    """
    Given a PDF's relative path (from PDF_DIR), return the URL for its thumbnail.
    Returns None if no thumbnail exists yet.
    """
    full_path = PDF_DIR / pdf_relative_path
    thumb     = _thumb_path(full_path)
    if thumb.exists():
        return f'/data-master/catalogue/thumb/{thumb.name}'
    return None


def invalidate_cache(pdf_path):
    """Remove a PDF's cache entry (e.g. when file is replaced)."""
    if _vk:
        _vk.delete(_cache_key(pdf_path))
    thumb = _thumb_path(pdf_path)
    if thumb.exists():
        thumb.unlink()


# ============================================================
#  BATCH GENERATE  (run as script)
# ============================================================
def generate_all(force=False):
    pdfs = list(PDF_DIR.glob('**/*.pdf'))
    print(f"\n  Found {len(pdfs)} PDFs in {PDF_DIR}")
    print(f"  Thumbnails → {THUMB_DIR}\n")

    done    = 0
    skipped = 0
    failed  = 0

    for i, pdf in enumerate(pdfs, 1):
        if not force and is_cached(pdf):
            skipped += 1
            continue

        print(f"  [{i:4d}/{len(pdfs)}] {pdf.name[:55]}...", end=' ', flush=True)
        result = generate_thumbnail(pdf)
        if result:
            print("✅")
            done += 1
        else:
            print("❌")
            failed += 1

    print(f"\n  ✅ Generated : {done}")
    print(f"  ⏭  Skipped   : {skipped} (already cached)")
    print(f"  ❌ Failed    : {failed}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate PDF thumbnails')
    parser.add_argument('--force', action='store_true', help='Regenerate all thumbnails')
    args = parser.parse_args()
    generate_all(force=args.force)