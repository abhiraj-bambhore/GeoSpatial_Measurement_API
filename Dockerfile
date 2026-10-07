# ─────────────────────────────────────────────
# Stage 1: Build — install deps with uv
# ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

# System deps for GDAL / Fiona / PyProj
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv via pip (most reliable on slim images)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy lockfiles first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install all production deps into a virtual environment
RUN uv venv .venv \
    && uv sync --no-dev --frozen

# ─────────────────────────────────────────────
# Stage 2: Runtime — lean final image
# ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime GDAL/Fiona system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring over the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Add venv to PATH
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy application source code
COPY app/ ./app/
COPY static/ ./static/
COPY migrations/ ./migrations/

# Create runtime directories owned by non-root user
RUN useradd -m -u 1001 appuser \
    && mkdir -p uploads data \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Healthcheck so Docker/Render knows when the container is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
