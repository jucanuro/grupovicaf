# syntax=docker/dockerfile:1
#
# Imagen multi-stage para GRUPO VICAF (LIMS + web institucional).
# Un único artefacto sirve a ambos sitios; el rol se decide en runtime con SITE_ROLE.

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# Dependencias de sistema necesarias solo para *compilar* las libs de Python
# (WeasyPrint/Pillow/lxml/cryptography traen extensiones C).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libpango1.0-dev \
        libcairo2-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

# Librerías de sistema que WeasyPrint necesita en RUNTIME (no en build).
# Sin estas, la generación de informes PDF falla al ejecutarse, no al construir la imagen.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN mkdir -p /app/staticfiles /app/mediafiles \
    && chown -R app:app /app /opt/venv

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=grupovicaf.settings.prod

USER app

EXPOSE 8000

CMD ["gunicorn", "grupovicaf.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
