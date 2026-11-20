# Developer Guide & Local Workflow

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.6  
**License:** Apache License 2.0  

---

## 1. Project Directory Structure

```text
Autonomous-Rocket-Landing/
├── backend/                   # FastAPI server, WebSocket handlers & session management
│   ├── app.py                 # Application entrypoint & HTTP/WS routes
│   ├── config.py              # Operational constants and environment configuration
│   ├── session_manager.py     # Concurrent simulation session pool & reaper
│   └── websocket_handler.py   # 50 Hz bi-directional WebSocket streaming loop
├── environments/              # Gymnasium Box2D physics wrappers
│   ├── custom_lander.py       # Custom aerodynamic forces and ground friction
│   └── reward_wrapper.py      # Reward shaping and evaluation interceptors
├── evaluation/                # Offline evaluation and statistical analysis tools
│   ├── evaluate.py            # Episode rollout engine with kinematic logging
│   ├── metrics.py             # Landing quality metrics and outcome classification
│   └── statistical_analysis.py# Paired t-tests, Holm-Bonferroni, and Wilson CI
├── models/                    # Trained Stable-Baselines3 PPO checkpoints
│   └── benchmark/             # Production models (Paradigms A, B, C, D across seeds)
├── tests/                     # Backend Pytest test suites (138 tests)
├── web/                       # React 19 / TypeScript / Vite frontend application
│   ├── src/
│   │   ├── components/        # Viewports, telemetry panels, header, debrief modal
│   │   ├── three/             # Procedural booster mesh, shaders & spaceport scene
│   │   ├── services/          # WebSocket client, jitter buffer & frame interpolator
│   │   ├── data/              # Reconciled benchmark datasets & statistical tables
│   │   └── types/             # Protocol schemas and snapshot interfaces
│   └── __tests__/             # Vitest frontend unit & integration suites (67 tests)
├── Dockerfile                 # Multi-stage production container build
├── requirements.txt           # Python backend dependencies
└── README.md                  # Main project documentation
```

---

## 2. Setting Up Local Development

### Prerequisites:
- Python `3.11.x`
- Node.js `20.x` or higher
- Git

### Backend Setup:
```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### Frontend Setup:
```bash
cd web
npm ci
cd ..
```

---

## 3. Running Test Suites

### Running Backend Tests:
```bash
pytest tests/
```
To run a specific test suite:
```bash
pytest tests/test_backend_websocket.py
pytest tests/test_backend_latch.py
```

### Running Frontend Tests:
```bash
npm test --prefix web -- --run
```

---

## 4. Running the Development Servers

For full-stack development with hot-reloading:

### Terminal 1: Backend Server
```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2: Frontend Vite Dev Server
```bash
cd web
npm run dev
```
Vite will host the frontend at `http://localhost:5173`, automatically proxying or connecting to WebSocket endpoint `ws://127.0.0.1:8000/ws/simulation`.
