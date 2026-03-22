# ============================================================
#  NET-1 — Django Application Container
#  Place this file at: net-1/main/Dockerfile
# ============================================================

FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Django source — .dockerignore keeps out venv, __pycache__, debugger etc.
COPY . .

# Create volume mount points so Django can write to them
RUN mkdir -p \
    /app/data/static \
    /app/data/media \
    /app/data/pdfs \
    /app/data/pdf_thumbs \
    /app/data/dumps \
    /app/data/exports \
    /app/logs

EXPOSE 8000

# Migrate then start Gunicorn
CMD ["sh", "-c", \
    "python manage.py migrate --noinput && \
     python manage.py collectstatic --noinput && \
     gunicorn core.wsgi:application \
       --bind 0.0.0.0:8000 \
       --workers 3 \
       --timeout 120 \
       --access-logfile - \
       --error-logfile -"]
