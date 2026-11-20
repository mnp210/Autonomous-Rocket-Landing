"""Configuration and operational constants for the backend simulation service."""

import os
from pathlib import Path

# Repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

# Default trained benchmark model path
DEFAULT_MODEL_PATH = (
    REPO_ROOT
    / "models"
    / "benchmark"
    / "D_curriculum_and_dr"
    / "seed_42"
    / "final_model.zip"
)

# Simulation Physics Parameters
PHYSICS_DT = 0.02  # 50 Hz authoritative Box2D stepping
DEFAULT_GRAVITY = -10.0
MAX_EPISODE_STEPS = 1200  # Hard cutoff to prevent runaway loops (24.0s sim-time)

# Concurrency & Scaling Limits
MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "30"))
SESSION_INACTIVITY_TIMEOUT_SEC = float(os.getenv("SESSION_INACTIVITY_TIMEOUT_SEC", "60.0"))
REAPER_INTERVAL_SEC = float(os.getenv("REAPER_INTERVAL_SEC", "10.0"))

# Network & WebSocket Security Limits
MAX_MESSAGE_PAYLOAD_BYTES = int(os.getenv("MAX_MESSAGE_PAYLOAD_BYTES", "4096"))  # 4 KB
MAX_INPUT_RATE_HZ = float(os.getenv("MAX_INPUT_RATE_HZ", "60.0"))  # Max 60 inputs/s per client

# Server network settings
SERVER_HOST = os.getenv("HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
