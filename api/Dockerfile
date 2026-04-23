# =============================================================================
# STAGE 1: builder — install dependencies
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (layer caching)
COPY requirements.txt .

# Install dependencies into a separate directory for copying later
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# =============================================================================
# STAGE 2: final — lean production image
# =============================================================================
FROM python:3.11-slim AS final

WORKDIR /app

# Create non-root user
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=appuser:appgroup main.py .

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn — bind to 0.0.0.0 so it's reachable outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
