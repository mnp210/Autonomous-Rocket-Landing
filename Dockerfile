# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Install dependencies
COPY web/package*.json ./
RUN npm ci

# Copy frontend source and compile production bundle
COPY web/ ./
RUN npm run build

# Stage 2: Python Backend Runtime (Hugging Face Spaces & Cloud Compatible)
FROM python:3.11-slim

# Avoid buffering and bytecode accumulation
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Install minimal OS build dependencies for Box2D C++ bindings and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    swig \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python runtime dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn[standard] websockets pydantic structlog psutil

# Copy application source code and models
COPY backend /app/backend
COPY environments /app/environments
COPY evaluation /app/evaluation
COPY rewards /app/rewards
COPY visualization /app/visualization
COPY models /app/models

# Copy compiled frontend distribution from builder stage
COPY --from=frontend-builder /build/dist /app/web/dist

# Non-root security user (UID 1000 compatible with HF Spaces & standard containers)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run Uvicorn ASGI server with dynamic port injection
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
