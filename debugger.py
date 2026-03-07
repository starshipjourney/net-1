import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

# ============================================================
#  Net-1 Project Debugger
#  Usage: python debugger.py <command> [target]
#  Example: python debugger.py test_conn postgres
#           python debugger.py test_conn valkey
#           python debugger.py test_conn all
# ============================================================

def header(title):
    print("=" * 50)
    print(f"  {title}")
    print("=" * 50)

def result(name, success, message):
    status = "✅" if success else "❌"
    print(f"{status} {name}: {message}")
    print("-" * 50)

# ------------------------------------------------------------
#  CONNECTION TESTS
# ------------------------------------------------------------

def test_postgres():
    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    result("PostgreSQL", True, version)

def test_valkey():
    from django.core.cache import cache
    cache.set('test_key', 'Valkey working net-1', 30)
    value = cache.get('test_key')
    if value:
        result("Valkey", True, f"got '{value}'")
    else:
        result("Valkey", False, "could not retrieve test value")

def test_conn(target="all"):
    header("Connection Tests")
    targets = {
        "postgres": test_postgres,
        "valkey": test_valkey,
    }
    if target == "all":
        for fn in targets.values():
            try:
                fn()
            except Exception as e:
                result(target, False, str(e))
    elif target in targets:
        try:
            targets[target]()
        except Exception as e:
            result(target, False, str(e))
    else:
        print(f"❌ Unknown target '{target}'. Available: {', '.join(targets.keys())}, all")

# ------------------------------------------------------------
#  COMMAND ROUTER
# ------------------------------------------------------------

COMMANDS = {
    "test_conn": test_conn,
    # future commands added here:
    # "test_models": test_models,
    # "test_celery": test_celery,
    # "test_api": test_api,
}

def show_help():
    header(" /n Net-1 Debugger — Available Commands")
    print("  test_conn [target]   Test database connections")
    print("  Targets: postgres, valkey, all")
    print()
    print("  Usage examples:")
    print("  python debugger.py test_conn all")
    print("  python debugger.py test_conn postgres")
    print("  python debugger.py test_conn valkey")
    print("=" * 50)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
    else:
        command = sys.argv[1]
        target = sys.argv[2] if len(sys.argv) > 2 else "all"

        if command in COMMANDS:
            COMMANDS[command](target)
        else:
            print(f"❌ Unknown command '{command}'")
            show_help()