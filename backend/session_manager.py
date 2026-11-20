"""Session Manager: Handles concurrency limits, model caching, and session lifecycle."""

import asyncio
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional
import structlog
from stable_baselines3 import PPO

from backend.config import (
    DEFAULT_MODEL_PATH,
    MAX_CONCURRENT_SESSIONS,
    REAPER_INTERVAL_SEC,
    SESSION_INACTIVITY_TIMEOUT_SEC,
)
from backend.schemas import FlightMode, PolicyMode, SessionInitPayload, StormSeverity
from backend.simulation_engine import SimulationSession

logger = structlog.get_logger(__name__)


class SessionManager:
    """Thread-safe registry for simulation sessions and shared PPO model inference."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path: Path = model_path or DEFAULT_MODEL_PATH
        self._model: Optional[PPO] = None
        self._model_lock = threading.Lock()

        # Session registries
        self._sessions: Dict[str, SimulationSession] = {}
        self._last_activity: Dict[str, float] = {}
        self._active_handlers: Dict[str, Any] = {}
        self._sessions_lock = threading.Lock()

        # Reaper task handle
        self._reaper_task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    def get_model(self) -> PPO:
        """Retrieves or lazily loads the pre-trained PPO policy model once into RAM."""
        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is None:
                if not self.model_path.exists():
                    raise FileNotFoundError(f"Model file not found at: {self.model_path}")
                logger.info("Loading pre-trained PPO model into memory", model_path=str(self.model_path))
                self._model = PPO.load(str(self.model_path))
                logger.info("PPO model loaded successfully")
        return self._model

    def create_session(self, payload: SessionInitPayload, session_id: Optional[str] = None) -> SimulationSession:
        """Instantiates and registers a new isolated simulation session."""
        with self._sessions_lock:
            if len(self._sessions) >= MAX_CONCURRENT_SESSIONS:
                raise RuntimeError(
                    f"Server capacity reached: {len(self._sessions)}/{MAX_CONCURRENT_SESSIONS} active sessions"
                )

            session = SimulationSession(
                session_id=session_id,
                mode=payload.mode,
                policy_mode=payload.policy_mode,
                seed=payload.seed,
                storm_severity=payload.storm_severity,
                wind=payload.wind,
                turbulence=payload.turbulence,
            )

            sid = session.session_id
            self._sessions[sid] = session
            self._last_activity[sid] = time.time()
            logger.info("Created simulation session", session_id=sid, mode=session.mode.value)
            return session

    def get_session(self, session_id: str) -> Optional[SimulationSession]:
        """Retrieves an active session and updates its last activity timestamp."""
        with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session is not None:
                self._last_activity[session_id] = time.time()
            return session

    def touch_session(self, session_id: str) -> None:
        """Refreshes the inactivity keepalive timer for a session."""
        with self._sessions_lock:
            if session_id in self._sessions:
                self._last_activity[session_id] = time.time()

    def remove_session(self, session_id: str) -> Optional[SimulationSession]:
        """Terminates and releases resources for a specific session."""
        with self._sessions_lock:
            session = self._sessions.pop(session_id, None)
            self._last_activity.pop(session_id, None)
            self._active_handlers.pop(session_id, None)

        if session is not None:
            session.close()
            logger.info("Terminated simulation session", session_id=session_id)
        return session

    def register_handler(self, session_id: str, handler: Any) -> Optional[Any]:
        """Registers the active WebSocket handler for a session, returning the previous handler if any."""
        with self._sessions_lock:
            prev = self._active_handlers.get(session_id)
            self._active_handlers[session_id] = handler
            return prev

    def unregister_handler(self, session_id: str, handler: Any) -> None:
        """Unregisters a handler if it is currently registered for the session."""
        with self._sessions_lock:
            if self._active_handlers.get(session_id) is handler:
                self._active_handlers.pop(session_id, None)

    @property
    def active_session_count(self) -> int:
        with self._sessions_lock:
            return len(self._sessions)

    def close_all(self) -> None:
        """Closes all active sessions cleanly on application shutdown."""
        with self._sessions_lock:
            sessions_to_close = list(self._sessions.values())
            self._sessions.clear()
            self._last_activity.clear()
            self._active_handlers.clear()

        for s in sessions_to_close:
            try:
                s.close()
            except Exception as e:
                logger.error("Error closing session", session_id=s.session_id, error=str(e))
        logger.info("All simulation sessions closed successfully")

    # =========================================================================
    # Async Background Reaper for Inactive / Dead Sessions
    # =========================================================================

    async def start_reaper(self) -> None:
        """Starts background garbage collection task for abandoned sessions."""
        if self._is_running:
            return
        self._is_running = True
        self._reaper_task = asyncio.create_task(self._reaper_loop())

    async def stop_reaper(self) -> None:
        """Cancels and awaits termination of the session reaper task."""
        self._is_running = False
        if self._reaper_task and not self._reaper_task.done():
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
        self._reaper_task = None

    async def _reaper_loop(self) -> None:
        """Periodically sweeps for expired sessions exceeding inactivity timeout."""
        while self._is_running:
            try:
                await asyncio.sleep(REAPER_INTERVAL_SEC)
                now = time.time()
                expired_ids = []

                with self._sessions_lock:
                    for sid, last_t in list(self._last_activity.items()):
                        if now - last_t > SESSION_INACTIVITY_TIMEOUT_SEC:
                            expired_ids.append(sid)

                for sid in expired_ids:
                    logger.warning("Reaping inactive session due to timeout", session_id=sid)
                    self.remove_session(sid)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in session reaper loop", error=str(e))
