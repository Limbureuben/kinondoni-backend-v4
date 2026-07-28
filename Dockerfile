# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_ENVIRONMENT=production \
    DJANGO_SETTINGS_MODULE=openspace.settings \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.prod.sh \
    && mkdir -p /app/media /app/staticfiles /app/logs \
    && addgroup --system appuser \
    && adduser --system --ingroup appuser appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; request=urllib.request.Request('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health/', headers={'Host':'localhost','X-Forwarded-Proto':'https'}); urllib.request.urlopen(request, timeout=3)"

ENTRYPOINT ["/app/entrypoint.prod.sh"]
CMD ["gunicorn", "openspace.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-"]
