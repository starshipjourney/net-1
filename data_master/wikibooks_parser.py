import os
import sys

MAIN_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR  = os.path.dirname(MAIN_DIR)

sys.path.append(MAIN_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from data_master.parser import parse_dump, get_latest_dump

DUMPS_DIR = os.path.join(BASE_DIR, 'data', 'dumps', 'wikibooks')

if __name__ == '__main__':
    dump_path = get_latest_dump(DUMPS_DIR)
    parse_dump(dump_path, source_type='wikibooks')