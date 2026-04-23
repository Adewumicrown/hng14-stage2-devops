# =============================================================================
# STAGE 1: builder — install dependencies
# =============================================================================
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files first (layer caching)
COPY package*.json ./

# Install all dependencies (including devDependencies if any)
RUN npm ci --omit=dev

# =============================================================================
# STAGE 2: final — lean production image
# =============================================================================
FROM node:18-alpine AS final

WORKDIR /app

# Create non-root user
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser

# Copy installed node_modules from builder
COPY --from=builder --chown=appuser:appgroup /app/node_modules ./node_modules

# Copy application source
COPY --chown=appuser:appgroup app.js .
COPY --chown=appuser:appgroup views/ ./views/
COPY --chown=appuser:appgroup package.json .

# Switch to non-root user
USER appuser

# Expose frontend port
EXPOSE 3000

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/health || exit 1

# Start the app
CMD ["node", "app.js"]
