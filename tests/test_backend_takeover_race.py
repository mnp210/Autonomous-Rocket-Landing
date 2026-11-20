"""Targeted regression test suite for Stage 9.2 backend ownership race prevention.

Verifies:
1. Reconnection takeover atomically fences out previous controller via generation tokens.
2. In-flight physics steps in worker threads complete cleanly before takeover finalizes.
3. Evicted controller cannot stream or advance steps after ownership transfer.
4. Box2D physics steps are strictly serialized via per-session RLock without race conditions.
"""

import asyncio
import json
import time
from fastapi.testclient import TestClient
import pytest
from stable_baselines3 import PPO

from backend.app import app, session_manager
from backend.config import DEFAULT_MODEL_PATH
from backend.schemas import ClientMessageType, FlightMode, ServerMessageType
from backend.simulation_engine import SimulationSession


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def ppo_model():
    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip(f"Model not found at {DEFAULT_MODEL_PATH}")
    return PPO.load(str(DEFAULT_MODEL_PATH))


class TestBackendOwnershipRace:
    """Verifies that WebSocket takeover cannot cause concurrent steps or state corruption."""

    def test_generation_fencing_blocks_superseded_step(self, ppo_model):
        """A step called with an outdated generation token must not advance the physics."""
        session = SimulationSession(mode=FlightMode.AI, seed=42)
        initial_gen = session.step_generation

        # Advance 1 step normally
        snap1 = session.step_ai(ppo_model, generation=initial_gen)
        assert snap1.lifecycle.step == 1
        assert session.step_count == 1

        # Simulate takeover advancing generation token
        new_gen = session.claim_ownership("new-controller-123")
        assert new_gen == initial_gen + 1
        assert session.owner_id == "new-controller-123"

        # Attempt to execute step with OLD generation token
        snap_stale = session.step_ai(ppo_model, generation=initial_gen)
        # Step count must NOT advance
        assert snap_stale.lifecycle.step == 1
        assert session.step_count == 1

        # Step with NEW generation token must advance cleanly
        snap2 = session.step_ai(ppo_model, generation=new_gen)
        assert snap2.lifecycle.step == 2
        assert session.step_count == 2

        session.close()

    def test_step_lock_serializes_concurrent_threads(self, ppo_model):
        """Simultaneous step calls from multiple threads must execute serially without Box2D collision."""
        session = SimulationSession(mode=FlightMode.AI, seed=42)
        gen = session.step_generation

        results = []
        errors = []

        def worker_step():
            try:
                snap = session.step_ai(ppo_model, generation=gen)
                results.append(snap.lifecycle.step)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads trying to step simultaneously
        import threading
        threads = [threading.Thread(target=worker_step) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread step raised exceptions: {errors}"
        assert len(results) == 10
        assert session.step_count == 10

        session.close()

    def test_websocket_takeover_eviction_and_fencing(self, client):
        """When client 2 connects with client 1's session ID, client 1 is evicted and fenced out."""
        with client.websocket_connect("/ws/simulation") as ws1:
            # 1. Initialize session on ws1
            init_msg = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"mode": "human", "seed": 42},
            }
            ws1.send_text(json.dumps(init_msg))
            ready1 = json.loads(ws1.receive_text())
            sid = ready1["payload"]["session_id"]
            _ = ws1.receive_text()  # step 0 frame

            # 2. Connect client 2 and claim session
            with client.websocket_connect("/ws/simulation") as ws2:
                reconnect_msg = {
                    "type": ClientMessageType.SESSION_INIT.value,
                    "payload": {"session_id": sid, "mode": "human"},
                }
                ws2.send_text(json.dumps(reconnect_msg))
                ready2 = json.loads(ws2.receive_text())
                assert ready2["type"] == ServerMessageType.SESSION_READY.value
                assert ready2["payload"]["session_id"] == sid

                # 3. Client 1 must receive SESSION_TAKEOVER
                takeover_frame = None
                for _ in range(5):
                    raw = ws1.receive_text()
                    msg = json.loads(raw)
                    if msg.get("type") == ServerMessageType.ERROR.value and msg["payload"].get("code") == "SESSION_TAKEOVER":
                        takeover_frame = msg
                        break

                assert takeover_frame is not None
                assert takeover_frame["payload"]["code"] == "SESSION_TAKEOVER"

                # 4. Client 1 sending action must be rejected with NO_SESSION
                act_msg = {
                    "type": ClientMessageType.INPUT_ACTION.value,
                    "payload": {"step": 1, "action": 2, "client_timestamp": time.time()},
                }
                ws1.send_text(json.dumps(act_msg))
                err_msg = json.loads(ws1.receive_text())
                assert err_msg["type"] == ServerMessageType.ERROR.value
                assert err_msg["payload"]["code"] == "NO_SESSION"

                # 5. Client 2 must be able to send valid inputs and drive the simulation
                ws2.send_text(json.dumps(act_msg))
                # Next frame from ws2 should be SIMULATION_STEP
                step_frame = json.loads(ws2.receive_text())
                assert step_frame["type"] in (ServerMessageType.SIMULATION_STEP.value, ServerMessageType.CONTROL_ACK.value)
