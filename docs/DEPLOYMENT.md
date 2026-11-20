# Deployment & Container Operations Guide

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.6  
**License:** Apache License 2.0  

---

## 1. Overview & Architectural Requirements

Autonomous Rocket Landing runs an authoritative, server-driven physics simulation where Box2D steps at **50 Hz** (20 ms interval) over persistent bi-directional WebSockets.

### Mandatory Hosting Characteristics:
1. **Long-Lived Container Process:** Ephemeral serverless platforms (AWS Lambda, Vercel Serverless) are **incompatible** because they cannot sustain background 50 Hz physics event loops.
2. **Persistent WebSockets:** Must support sustained WebSocket connections with minimal proxy jitter.
3. **Low Latency Single-Core CPU:** Step compute takes ~0.31 ms; CPU throttling must not exceed 20 ms per tick.

---

## 2. Multi-Stage Docker Container Build

The application is packaged via a self-contained multi-stage [`Dockerfile`](file:///d:/Projects/Autonomous-Rocket-Landing/Dockerfile):

```dockerfile
# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python Backend Runtime
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    swig \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY environments /app/environments
COPY evaluation /app/evaluation
COPY rewards /app/rewards
COPY visualization /app/visualization
COPY models /app/models

COPY --from=frontend-builder /build/dist /app/web/dist

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

### Local Docker Build & Execution:
```bash
# Build production image
docker build -t autonomous-rocket-landing .

# Run container on port 8080
docker run -p 8080:8080 -e MAX_CONCURRENT_SESSIONS=20 autonomous-rocket-landing
```
Access the application at `http://localhost:8080`.

---

## 3. Zero-Cost Production Hosting Platforms

### Primary Recommendation: Hugging Face Spaces (Docker SDK)
- **Free Tier Resources:** 2 vCPU, 16 GB RAM, 50 GB persistent disk.
- **Cost:** **$0.00** forever; zero credit card requirement.
- **WebSocket Routing:** Native support without proxy drops.
- **Idle Behavior:** Enters sleep mode after 48 hours of total inactivity; cold start on first HTTP visit takes ~5 seconds.
- **Deployment Procedure:**
  1. Create a new Space on [Hugging Face](https://huggingface.co/new-space).
  2. Select **Docker** as Space SDK (Blank template).
  3. Push repository to the Space remote:
     ```bash
     git remote add space https://huggingface.co/spaces/<USERNAME>/autonomous-rocket-landing
     git push space main
     ```

### Secondary Mirror: Render (Web Service)
- **Free Tier Resources:** 0.1 vCPU, 512 MB RAM, 750 free instance hours per month.
- **Deployment Setting:** Set environment variable `MAX_CONCURRENT_SESSIONS=5` to prevent 0.1 vCPU throttling under multi-user access.
- **Idle Behavior:** Spins down after 15 minutes of inactivity; cold start takes ~50–90 seconds.
