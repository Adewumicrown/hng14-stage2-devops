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

# Install dependencies into a separate prefix directory
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
COPY --chown=appuser:appgroup worker.py .

# Switch to non-root user
USER appuser

# Health check — verify the worker process is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import redis, os; r = redis.Redis(host=os.environ.get('REDIS_HOST','redis'), port=int(os.environ.get('REDIS_PORT', 6379))); r.ping()" || exit 1

# Run the worker
CMD ["python", "worker.py"]
