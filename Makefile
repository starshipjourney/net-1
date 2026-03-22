# ============================================================
#  NET-1 — Makefile
#  Place at: net-1/Makefile
#  Usage: make <target>
# ============================================================

.PHONY: help setup up down restart build logs logs-app shell bash migrate superuser static clean

help:
	@echo ""
	@echo "  NET-1 Commands"
	@echo "  ──────────────────────────────────────"
	@echo "  make setup      — first-time: build, migrate, collectstatic"
	@echo "  make up         — start all containers"
	@echo "  make down       — stop all containers"
	@echo "  make restart    — restart django container only"
	@echo "  make build      — rebuild django image"
	@echo "  make logs       — follow all container logs"
	@echo "  make logs-app   — follow django logs only"
	@echo "  make shell      — open Django python shell"
	@echo "  make bash       — open bash in django container"
	@echo "  make migrate    — run database migrations"
	@echo "  make superuser  — create superuser account"
	@echo "  make static     — collect static files"
	@echo "  make clean      — remove all containers (keeps data)"
	@echo ""

# ── First-time setup ─────────────────────────────────────────
setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ""; \
		echo "  ⚠  .env created from .env.example"; \
		echo "  ✏  Edit .env with your values then run 'make setup' again"; \
		echo ""; \
		exit 1; \
	fi
	@mkdir -p data/db/postgres data/db/valkey data/ollama \
	          data/media data/pdfs data/pdf_thumbs \
	          data/static data/dumps data/exports logs
	podman-compose build django
	podman-compose up -d postgres valkey ollama
	@echo "Waiting for postgres to be ready..."
	@sleep 8
	podman-compose up -d django
	@echo ""
	@echo "✅ NET-1 is running."
	@echo "   Run 'make superuser' to create your admin account."
	@echo "   Then visit http://localhost:8000"
	@echo ""

# ── Day-to-day ───────────────────────────────────────────────
up:
	podman-compose up -d

down:
	podman-compose down

restart:
	podman-compose restart django

build:
	podman-compose build django

logs:
	podman-compose logs -f

logs-app:
	podman-compose logs -f django

# ── Django management ─────────────────────────────────────────
shell:
	podman-compose exec django python manage.py shell

bash:
	podman-compose exec django /bin/bash

migrate:
	podman-compose exec django python manage.py migrate --noinput

superuser:
	podman-compose exec django python manage.py createsuperuser

static:
	podman-compose exec django python manage.py collectstatic --noinput

# ── Cleanup (keeps data volumes intact) ──────────────────────
clean:
	podman-compose down --remove-orphans
	@echo "Containers stopped and removed. Data in data/ is untouched."
