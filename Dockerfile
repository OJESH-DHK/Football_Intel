# syntax=docker/dockerfile:1

# ---------- Stage 1: builder ----------
# Compiles wheels (needs build toolchain). Nothing here ships to the final image.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG INSTALL_DEV=false
COPY requirements.txt requirements-dev.txt ./

# Build all deps into a wheel dir so the runtime stage installs without a compiler.
RUN pip install --upgrade pip && \
    if [ "$INSTALL_DEV" = "true" ]; then \
        pip wheel --wheel-dir /wheels -r requirements-dev.txt; \
    else \
        pip wheel --wheel-dir /wheels -r requirements.txt; \
    fi

# ---------- Stage 2: runtime ----------
# Slim final image: only the runtime libpq + prebuilt wheels. No compiler.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# libpq5 = Postgres client runtime lib (psycopg needs it). curl = healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install from prebuilt wheels — fast, no toolchain in final layer.
COPY --from=builder /wheels /wheels
COPY requirements.txt requirements-dev.txt ./
ARG INSTALL_DEV=false
RUN pip install --no-index --find-links=/wheels \
        $([ "$INSTALL_DEV" = "true" ] && echo "-r requirements-dev.txt" || echo "-r requirements.txt") \
    && rm -rf /wheels

# Create non-root user before copying so files land with correct owner.
RUN addgroup --system django && adduser --system --ingroup django django

COPY --chown=django:django . .

# Collect static at build time (whitenoise serves them; nginx mounts the volume).
# Dummy env only satisfies settings import — collectstatic opens no DB/Redis socket.
# No `|| true`: a real failure must break the build, not silently ship 0 files.
RUN SECRET_KEY=build-only \
    DATABASE_URL=sqlite:////tmp/build.db \
    REDIS_URL=redis://localhost:6379/0 \
    CELERY_BROKER_URL=redis://localhost:6379/0 \
    CELERY_RESULT_BACKEND=redis://localhost:6379/0 \
    python manage.py collectstatic --noinput

USER django

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/ || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
