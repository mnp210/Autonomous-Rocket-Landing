# Stage 9.5 — Deep Hosting Evaluation & Zero-Cost Strategy

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.5 — Full Application Integration & Deployment Readiness  
**Date:** 2026-11-20  
**Status:** COMPLETE & ACCEPTED  

---

## 1. Executive Summary

Autonomous Rocket Landing runs an authoritative, server-driven physics simulation where the physical state steps continuously at **50 Hz** (20 ms interval) over persistent bi-directional WebSockets. This fundamental technical characteristic creates hosting requirements distinct from typical static sites or standard CRUD REST APIs.

This evaluation examines cloud hosting options with an uncompromising constraint: **Guaranteed Zero-Cost ($0.00) Operation without credit card traps, sudden tier expiration, or hidden billing spikes.**

---

## 2. Empirical Performance & Capacity Benchmarks

Hardware capacity benchmarks were empirically measured on the project's production stack (Python 3.11, PyTorch CPU, Stable-Baselines3 PPO, Box2D C++ bindings, FastAPI, Uvicorn) using `scratch/benchmark_stage9_5_performance.py`:

```
================================================================================
AUTONOMOUS ROCKET LANDING — BENCHMARK RESULTS (STAGE 9.5)
================================================================================
Timestamp:               2026-11-20T16:38:22Z
Base Process RSS:        223.75 MB
RAM with PPO in Memory:  291.02 MB (+67.27 MB delta)
Model Cold Load Time:    1,327.35 ms
Session Initialization:  20.04 ms

Step Micro-latencies (500 steps):
  PPO Inference:         0.231 ms (p95: 0.275 ms, max: 0.512 ms)
  Box2D Physics:         0.052 ms (p95: 0.068 ms, max: 0.124 ms)
  JSON Serialization:    0.008 ms (p95: 0.010 ms, max: 0.021 ms)
  Total Step Compute:    0.312 ms (p95: 0.369 ms, p99: 0.443 ms)

Snapshot Payload Size:   710 bytes (35.5 KB/s outbound per session @ 50 Hz)
Throughput (Single Core):3,381.4 Steps/sec (SPS)

Concurrency Model (70% CPU Target):
  Theoretical Safe Max:  47 concurrent sessions per 1 vCPU
  Practical Safe Limit:  15–20 concurrent sessions (1 vCPU)
  Practical Safe Limit:  30–40 concurrent sessions (2 vCPU)
================================================================================
```

### Key Takeaways:
1. **Negligible Step Compute:** Box2D physics plus PPO neural network inference consume only **0.312 ms** per step—less than **1.6%** of the 20.0 ms budget between frames.
2. **Lean Memory Footprint:** The entire backend with PyTorch, Gymnasium, Box2D, and the trained Stage D PPO checkpoint consumes just **291 MB of RAM**, fitting comfortably inside a 512 MB or 1 GB container.
3. **Outbound Network Bandwidth:** Each active 50 Hz flight produces ~35.5 KB/s (2.13 MB/minute). A 10-minute active landing session consumes ~21.3 MB of outbound transfer.

---

## 3. The Continuous Simulation Hosting Challenge

Why conventional web hosting architectures fail for this application:

1. **Serverless Incompatibility (AWS Lambda, Vercel Functions, Cloudflare Workers):**
   - Serverless functions are stateless, ephemeral, request-driven workers.
   - They cannot host an active, persistent 50 Hz simulation loop (`while True: env.step()`).
   - Serverless WebSocket adapters require external pub/sub layers (e.g., Redis, DynamoDB) to coordinate state between requests, adding unacceptable round-trip latency (>50–100 ms) that destroys the 20 ms physics cadence.
2. **Persistent Container Requirement:**
   - The application requires a long-lived container process running an ASGI event loop (Uvicorn) with persistent memory holding Box2D C++ state and the loaded PyTorch PPO model.
3. **Continuous vCPU Consumption on WebSockets:**
   - On platforms that bill per vCPU-second of connection time (e.g. Google Cloud Run), a single visitor holding an active WebSocket for 1 hour consumes 3,600 vCPU-seconds.
   - With 100 concurrent visitor-hours, monthly free allowances are rapidly depleted, risking unexpected credit card charges.

---

## 4. Platform Comparison & Evaluation Matrix

| Platform | Free Tier Resources | Credit Card Required? | WebSocket Support | Sleep / Cold Start Behavior | 50 Hz Concurrency Risk | Cost Risk Rating |
| :--- | :--- | :---: | :---: | :--- | :--- | :---: |
| **Hugging Face Spaces (Docker)** | **2 vCPU, 16 GB RAM, 50 GB Disk** | **NO** | Native & Persistent | Sleeps after 48h idle; wakes on HTTP (~5–10s) | None (2 vCPU easily handles 30+ sessions) | **ZERO RISK (Recommended)** |
| **Render (Web Service)** | 0.1 vCPU, 512 MB RAM, 750 hrs/month | NO | Supported | Spins down after 15m idle; cold start 50–90s | HIGH (0.1 vCPU shared causes stepping jitter) | Low (hard stopped at 750h) |
| **Google Cloud Run** | 2M reqs, 360k vCPU-s, 180k GiB-s | **YES** | Native (1 hr limit) | Instant scaling from 0 to 1 instance | None (dedicated vCPU) | **HIGH (Charges credit card when free vCPU-s exhausted)** |
| **Fly.io** | No free tier without card | **YES** | Native | Auto-stop/start available | Low | **HIGH (Requires active billing)** |
| **Vercel / Netlify** | Serverless only | NO | Serverless WS only | Incompatible with continuous 50 Hz physics | Fatal (Architecture mismatch) | Incompatible |

---

## 5. Hosting Architecture Recommendations

### Recommended Primary Platform: Hugging Face Spaces (Docker)
- **Why:** 100% free forever without providing credit card information. Generous resource ceiling: **2 dedicated vCPUs and 16 GB of RAM**, dwarfing the application's 291 MB requirement.
- **WebSocket Protocol:** Seamlessly routes bi-directional WebSockets without proxy disconnects.
- **Idle Behavior:** The space goes to sleep only after **48 hours** of zero activity (compared to Render's aggressive 15-minute shutdown). First visit after sleep triggers an automated container boot in ~5 seconds.
- **Packaging:** Multi-stage `Dockerfile` compiles the React frontend (`web/dist`) and mounts it statically in FastAPI (`/`), exposing both the UI and WebSockets (`/ws/simulation`) on port 7860/8080.

### Recommended Secondary Platform: Render (Free Web Service)
- Useful as an alternative mirror.
- Requires setting `MAX_CONCURRENT_SESSIONS=5` to prevent 0.1 vCPU throttling under multi-user access.

---

## 6. Capacity & Cost Conclusion

| Metric | Measured Specification | Hugging Face Spaces (Free) | Render (Free) |
| :--- | :--- | :--- | :--- |
| **Monthly Cost** | — | **$0.00** | **$0.00** |
| **Credit Card on File** | — | **None** | **None** |
| **RAM Utilization** | 291 MB | 1.8% of 16 GB | 56.8% of 512 MB |
| **CPU Utilization (1 session)** | 1.56% of 1 core | 0.78% of 2 vCPUs | 15.6% of 0.1 vCPU |
| **Safe Concurrent Sessions** | — | **30 sessions** | **4–5 sessions** |
| **Outbound Transfer Ceiling** | 35.5 KB/s / user | Unlimited community bandwidth | 100 GB/month limit |
