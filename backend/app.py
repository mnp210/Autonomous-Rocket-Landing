"""FastAPI Simulation Backend Application Entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import structlog

from backend.config import CORS_ORIGINS, DEFAULT_MODEL_PATH, MAX_CONCURRENT_SESSIONS
from backend.session_manager import SessionManager
from backend.websocket_handler import WebSocketSimulationHandler

logger = structlog.get_logger(__name__)

# Global singleton session manager
session_manager = SessionManager(model_path=DEFAULT_MODEL_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown."""
    logger.info("Initializing Autonomous Rocket Landing Backend Service")

    # 1. Warm-up preloaded PPO model in memory
    try:
        session_manager.get_model()
        logger.info("PPO model preloaded successfully into RAM")
    except Exception as e:
        logger.error("Failed to load preloaded model at startup", error=str(e))

    # 2. Start background session reaper
    await session_manager.start_reaper()
    logger.info("Session reaper task started")

    yield

    # 3. Graceful shutdown
    logger.info("Shutting down backend service...")
    await session_manager.stop_reaper()
    session_manager.close_all()
    logger.info("All resources released cleanly")


app = FastAPI(
    title="Autonomous Rocket Landing Simulation API",
    description="Real-time WebSocket simulation service exposing Box2D physics and trained PPO inference.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup for web client connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Service health and concurrency capacity status."""
    return {
        "status": "ok",
        "active_sessions": session_manager.active_session_count,
        "max_concurrent_sessions": MAX_CONCURRENT_SESSIONS,
        "model_loaded": session_manager._model is not None,
    }


@app.get("/api/info")
async def simulation_info():
    """Environment specifications and action space documentation."""
    return {
        "environment": "LunarLander-v3",
        "physics_engine": "Box2D (2D Planar)",
        "timestep_dt": 0.02,
        "frequency_hz": 50.0,
        "action_space": {
            0: "Coast (No Thrusters)",
            1: "Left RCS Thruster",
            2: "Main Descent Engine",
            3: "Right RCS Thruster",
        },
        "observation_space": [
            "pos_x (Box2D units)",
            "pos_y (Box2D units)",
            "vel_x (m/s)",
            "vel_y (m/s)",
            "angle (radians)",
            "angular_velocity (rad/s)",
            "left_contact (bool)",
            "right_contact (bool)",
        ],
        "model": {
            "algorithm": "PPO",
            "framework": "Stable-Baselines3",
            "checkpoint": "benchmark_D_curriculum_and_dr_seed42",
        },
    }


@app.websocket("/ws/simulation")
async def websocket_simulation_endpoint(websocket: WebSocket):
    """Real-time bi-directional WebSocket simulation communication endpoint."""
    handler = WebSocketSimulationHandler(websocket=websocket, session_manager=session_manager)
    await handler.handle_connection()


# Mount frontend production build if available
from pathlib import Path
from fastapi.staticfiles import StaticFiles

web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="frontend")

