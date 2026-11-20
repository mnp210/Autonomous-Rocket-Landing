"""WebSocket simulation stream handler for real-time client interaction."""

import asyncio
import json
import time
from typing import Optional
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError
import structlog

from backend.config import MAX_INPUT_RATE_HZ, MAX_MESSAGE_PAYLOAD_BYTES, PHYSICS_DT
from backend.schemas import (
    ClientControlMessage,
    ClientInitMessage,
    ClientInputMessage,
    ClientMessageType,
    ClientPingMessage,
    EpisodeCompletePayload,
    ErrorPayload,
    FlightMode,
    HeartbeatPongPayload,
    ServerControlAckMessage,
    ServerEpisodeCompleteMessage,
    ServerErrorMessage,
    ServerMessageType,
    ServerPongMessage,
    ServerSessionReadyMessage,
    ServerSimulationStepMessage,
)
from backend.session_manager import SessionManager
from backend.simulation_engine import SimulationSession

logger = structlog.get_logger(__name__)


class WebSocketSimulationHandler:
    """Manages the full lifecycle of a single WebSocket simulation client connection."""

    def __init__(self, websocket: WebSocket, session_manager: SessionManager):
        self.ws: WebSocket = websocket
        self.session_manager: SessionManager = session_manager
        self.session: Optional[SimulationSession] = None
        self.is_connected: bool = True
        self.handler_id: str = str(uuid.uuid4())
        self.generation: int = 1

        # Human input buffer & step tracking
        self.buffered_human_action: int = 0
        self.last_client_step: int = -1

        # Rate limiter state (Token Bucket: max burst 5, fill rate MAX_INPUT_RATE_HZ)
        self.last_input_time: float = time.time()
        self.input_tokens: float = 5.0

        # Async background stepping task
        self.sim_loop_task: Optional[asyncio.Task] = None

    async def handle_connection(self) -> None:
        """Main lifecycle entrypoint for the WebSocket connection."""
        await self.ws.accept()
        logger.info("WebSocket client connected", client=str(self.ws.client))

        try:
            while self.is_connected:
                raw_text = await self.ws.receive_text()

                # 1. Payload size guard
                if len(raw_text.encode("utf-8")) > MAX_MESSAGE_PAYLOAD_BYTES:
                    await self._send_error("PAYLOAD_TOO_LARGE", f"Maximum message size is {MAX_MESSAGE_PAYLOAD_BYTES} bytes")
                    continue

                # 2. Parse JSON
                try:
                    data = json.loads(raw_text)
                except Exception:
                    await self._send_error("MALFORMED_JSON", "Message must be valid JSON")
                    continue

                # 3. Dispatch message based on type
                msg_type = data.get("type")
                if not msg_type:
                    await self._send_error("MISSING_TYPE", "Message missing 'type' field")
                    continue

                await self._dispatch_message(msg_type, data)

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected normally", client=str(self.ws.client))
        except Exception as e:
            logger.error("Unhandled exception in WebSocket loop", error=str(e), client=str(self.ws.client))
        finally:
            self.is_connected = False
            await self._cleanup()

    async def _dispatch_message(self, msg_type: str, data: dict) -> None:
        """Validates and routes incoming messages to respective handlers."""
        # 1. Heartbeat Ping (Allowed before session creation)
        if msg_type == ClientMessageType.HEARTBEAT_PING.value:
            try:
                msg = ClientPingMessage.model_validate(data)
                pong = ServerPongMessage(
                    payload=HeartbeatPongPayload(
                        ping_timestamp=msg.payload.timestamp,
                        server_timestamp=time.time(),
                    )
                )
                await self.ws.send_text(pong.model_dump_json())
                if self.session:
                    self.session_manager.touch_session(self.session.session_id)
            except ValidationError as ve:
                await self._send_error("VALIDATION_ERROR", str(ve))
            return

        # 2. Session Initialization
        if msg_type == ClientMessageType.SESSION_INIT.value:
            try:
                msg = ClientInitMessage.model_validate(data)
                await self._handle_session_init(msg)
            except ValidationError as ve:
                await self._send_error("VALIDATION_ERROR", str(ve))
            return

        # Subsequent messages require an active session
        if self.session is None:
            await self._send_error("NO_SESSION", "Must initialize session via SESSION_INIT first")
            return

        # 3. Input Action (Human Pilot Mode)
        if msg_type == ClientMessageType.INPUT_ACTION.value:
            if self.session.mode != FlightMode.HUMAN:
                await self._send_error("INVALID_MODE", f"Cannot send INPUT_ACTION in mode '{self.session.mode.value}'. Mode must be 'human'.")
                return

            if self.session.is_done():
                await self._send_error("EPISODE_TERMINATED", "Cannot accept inputs after episode has finished.")
                return

            try:
                msg = ClientInputMessage.model_validate(data)
            except ValidationError as ve:
                await self._send_error("VALIDATION_ERROR", str(ve))
                return

            # Enforce sequential order
            if msg.payload.step < self.last_client_step:
                await self._send_error("STALE_STEP", f"Input step {msg.payload.step} is older than last received step {self.last_client_step}")
                return

            # Rate limiting check (Token bucket with burst capacity of 5)
            now = time.time()
            elapsed = now - self.last_input_time
            self.last_input_time = now
            self.input_tokens = min(5.0, self.input_tokens + elapsed * MAX_INPUT_RATE_HZ)
            if self.input_tokens < 1.0:
                # Discard burst exceeding inputs to protect server stepping
                return
            self.input_tokens -= 1.0

            self.last_client_step = msg.payload.step
            self.buffered_human_action = msg.payload.action
            self.session_manager.touch_session(self.session.session_id)
            return

        # 4. Control Commands (Pause, Resume, Reset, Set Speed)
        if msg_type == ClientMessageType.CONTROL_CMD.value:
            try:
                msg = ClientControlMessage.model_validate(data)
                await self._handle_control_cmd(msg)
                self.session_manager.touch_session(self.session.session_id)
            except ValidationError as ve:
                await self._send_error("VALIDATION_ERROR", str(ve))
            return

        await self._send_error("UNSUPPORTED_TYPE", f"Unknown message type '{msg_type}'")

    async def _handle_session_init(self, msg: ClientInitMessage) -> None:
        """Creates an isolated simulation session or reconnects to an existing one, and begins stepping."""
        # Cancel any existing simulation loop on this connection
        if self.sim_loop_task and not self.sim_loop_task.done():
            self.sim_loop_task.cancel()

        # Handle reconnection attempt
        if msg.payload.session_id:
            existing = self.session_manager.get_session(msg.payload.session_id)
            if existing is None:
                await self._send_error("SESSION_EXPIRED", f"Session '{msg.payload.session_id}' has expired or does not exist")
                return
            self.session = existing
        else:
            # Clean up old session if this connection owned one
            if self.session:
                self.session_manager.remove_session(self.session.session_id)

            try:
                self.session = self.session_manager.create_session(msg.payload)
            except RuntimeError as re:
                await self._send_error("SERVER_CAPACITY_EXCEEDED", str(re))
                return

        # Ensure single-controller exclusivity: displace any prior handler
        prev_handler = self.session_manager.register_handler(self.session.session_id, self)
        if prev_handler is not None and prev_handler is not self:
            await prev_handler.evict("SESSION_TAKEOVER", "A new connection has claimed control of this session")

        # Claim ownership generation token, waiting for any in-flight physics step from old handler
        self.generation = await asyncio.to_thread(self.session.claim_ownership, self.handler_id)

        # Send initial static geometry and session ready confirmation
        ready_msg = ServerSessionReadyMessage(payload=self.session.get_session_ready_payload())
        await self.ws.send_text(ready_msg.model_dump_json())

        # Send initial Step 0 snapshot
        init_snap = ServerSimulationStepMessage(payload=self.session.extract_snapshot())
        await self.ws.send_text(init_snap.model_dump_json())

        # Start asynchronous stepping loop
        self.sim_loop_task = asyncio.create_task(self._simulation_loop())

    async def evict(self, code: str, message: str) -> None:
        """Evicts this handler when another connection claims exclusive control of the session."""
        if self.sim_loop_task and not self.sim_loop_task.done():
            self.sim_loop_task.cancel()
            try:
                await self.sim_loop_task
            except asyncio.CancelledError:
                pass
            self.sim_loop_task = None

        await self._send_error(code, message)
        self.session = None
        self.is_connected = False

    async def _handle_control_cmd(self, msg: ClientControlMessage) -> None:
        """Processes simulation control flow operations."""
        cmd = msg.payload.command
        val = msg.payload.value

        if cmd == "pause":
            self.session.is_paused = True
            ack = ServerControlAckMessage(payload={"command": "pause", "status": "paused"})
            await self.ws.send_text(ack.model_dump_json())

        elif cmd == "resume":
            self.session.is_paused = False
            ack = ServerControlAckMessage(payload={"command": "resume", "status": "running"})
            await self.ws.send_text(ack.model_dump_json())

        elif cmd == "reset":
            new_seed = int(val) if val is not None else None
            snap_reset = self.session.reset(new_seed=new_seed)
            self.buffered_human_action = 0
            self.last_client_step = -1

            ack = ServerControlAckMessage(payload={"command": "reset", "seed": self.session.seed})
            await self.ws.send_text(ack.model_dump_json())

            # Broadcast new step 0 state
            step_msg = ServerSimulationStepMessage(payload=snap_reset)
            await self.ws.send_text(step_msg.model_dump_json())

        elif cmd == "set_speed":
            if val is not None and 0.1 <= val <= 2.0:
                self.session.speed_factor = float(val)
                ack = ServerControlAckMessage(payload={"command": "set_speed", "speed": self.session.speed_factor})
                await self.ws.send_text(ack.model_dump_json())

    async def _simulation_loop(self) -> None:
        """Asynchronous physics stepping loop running at up to 50 Hz with drift compensation."""
        model = self.session_manager.get_model()
        target_dt = PHYSICS_DT / max(0.1, self.session.speed_factor)
        next_tick = time.perf_counter()

        while self.is_connected and self.session is not None:
            # Fencing check: if generation changed or evicted, terminate loop
            if self.session.owner_id != self.handler_id:
                break

            target_dt = PHYSICS_DT / max(0.1, self.session.speed_factor)

            if not self.session.is_paused and not self.session.is_done():
                gen = self.generation
                # Execute step in worker thread to prevent blocking async event loop
                if self.session.mode in (FlightMode.AI, FlightMode.STORM):
                    snapshot = await asyncio.to_thread(self.session.step_ai, model, gen)
                else:
                    action = self.buffered_human_action
                    snapshot = await asyncio.to_thread(self.session.step_human, action, gen)

                # Check if this connection was evicted while to_thread was executing
                if not self.is_connected or self.session is None or self.session.owner_id != self.handler_id:
                    break

                # Stream snapshot
                step_msg = ServerSimulationStepMessage(payload=snapshot)
                await self.ws.send_text(step_msg.model_dump_json())

                # If episode reached completion, transmit debrief
                if self.session.is_done():
                    comp_payload = self.session.get_episode_complete_payload()
                    comp_msg = ServerEpisodeCompleteMessage(payload=comp_payload)
                    await self.ws.send_text(comp_msg.model_dump_json())

            # Wall-clock anchor scheduling with lag guard
            next_tick += target_dt
            now = time.perf_counter()
            sleep_time = next_tick - now

            if sleep_time > 0.001:
                await asyncio.sleep(sleep_time)
            else:
                # If falling behind by more than 2 frames, re-anchor to current time
                if (now - next_tick) > (2.0 * target_dt):
                    next_tick = now
                await asyncio.sleep(0.001)

    async def _send_error(self, code: str, message: str) -> None:
        """Sends a structured error packet to the client."""
        err = ServerErrorMessage(payload=ErrorPayload(code=code, message=message))
        try:
            await self.ws.send_text(err.model_dump_json())
        except Exception:
            pass

    async def _cleanup(self) -> None:
        """Cancels simulation tasks and releases session resources cleanly."""
        if self.sim_loop_task and not self.sim_loop_task.done():
            self.sim_loop_task.cancel()
            try:
                await self.sim_loop_task
            except asyncio.CancelledError:
                pass
            self.sim_loop_task = None

        if self.session:
            sid = self.session.session_id
            self.session_manager.unregister_handler(sid, self)
            self.session_manager.remove_session(sid)
            self.session = None
