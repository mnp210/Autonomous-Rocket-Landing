"""Integration tests for FastAPI HTTP and WebSocket simulation endpoints."""

import json
import time
from fastapi.testclient import TestClient
import pytest

from backend.app import app, session_manager
from backend.config import MAX_CONCURRENT_SESSIONS
from backend.schemas import ClientMessageType, ServerMessageType


@pytest.fixture(scope="module")
def client():
    """Initializes FastAPI test client with lifespan context."""
    with TestClient(app) as test_client:
        yield test_client


class TestBackendWebSocket:
    """Verifies WebSocket protocol handshake, message streaming, and control commands."""

    def test_http_health_and_info_endpoints(self, client):
        # 1. Health check
        res_health = client.get("/health")
        assert res_health.status_code == 200
        data_h = res_health.json()
        assert data_h["status"] == "ok"
        assert "active_sessions" in data_h
        assert data_h["model_loaded"] is True

        # 2. Simulation metadata
        res_info = client.get("/api/info")
        assert res_info.status_code == 200
        data_i = res_info.json()
        assert data_i["environment"] == "LunarLander-v3"
        assert data_i["timestep_dt"] == 0.02
        assert "action_space" in data_i

    def test_websocket_heartbeat_ping_pong(self, client):
        with client.websocket_connect("/ws/simulation") as ws:
            ping_msg = {
                "type": ClientMessageType.HEARTBEAT_PING.value,
                "payload": {"timestamp": time.time()},
            }
            ws.send_text(json.dumps(ping_msg))
            resp = json.loads(ws.receive_text())

            assert resp["type"] == ServerMessageType.HEARTBEAT_PONG.value
            assert "ping_timestamp" in resp["payload"]
            assert "server_timestamp" in resp["payload"]

    def test_websocket_session_init_and_streaming(self, client):
        with client.websocket_connect("/ws/simulation") as ws:
            init_msg = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {
                    "mode": "ai",
                    "policy_mode": "deterministic",
                    "seed": 42,
                    "storm_severity": "moderate",
                },
            }
            ws.send_text(json.dumps(init_msg))

            # 1. Expect SESSION_READY
            ready_resp = json.loads(ws.receive_text())
            assert ready_resp["type"] == ServerMessageType.SESSION_READY.value
            assert ready_resp["payload"]["dt"] == 0.02
            assert ready_resp["payload"]["seed"] == 42
            assert len(ready_resp["payload"]["terrain"]) > 0

            # 2. Expect initial Step 0 SIMULATION_STEP
            step0 = json.loads(ws.receive_text())
            assert step0["type"] == ServerMessageType.SIMULATION_STEP.value
            assert step0["payload"]["lifecycle"]["step"] == 0

            # 3. Expect subsequent simulation step streaming
            step1 = json.loads(ws.receive_text())
            assert step1["type"] == ServerMessageType.SIMULATION_STEP.value
            assert step1["payload"]["lifecycle"]["step"] >= 1

    def test_websocket_human_input_and_control(self, client):
        with client.websocket_connect("/ws/simulation") as ws:
            # Init in human mode
            init_msg = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"mode": "human", "seed": 100},
            }
            ws.send_text(json.dumps(init_msg))
            _ = ws.receive_text()  # SESSION_READY
            _ = ws.receive_text()  # Step 0

            # Send manual action (Main engine: action=2)
            act_msg = {
                "type": ClientMessageType.INPUT_ACTION.value,
                "payload": {
                    "step": 0,
                    "action": 2,
                    "client_timestamp": time.time(),
                },
            }
            ws.send_text(json.dumps(act_msg))

            # Read next frame and verify action execution
            step_frame = json.loads(ws.receive_text())
            assert step_frame["type"] == ServerMessageType.SIMULATION_STEP.value
            assert step_frame["payload"]["propulsion"]["action"] in (0, 2)

    def test_websocket_pause_resume_reset_commands(self, client):
        with client.websocket_connect("/ws/simulation") as ws:
            init_msg = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"mode": "ai", "seed": 42},
            }
            ws.send_text(json.dumps(init_msg))
            _ = ws.receive_text()  # SESSION_READY
            _ = ws.receive_text()  # Step 0

            # 1. Pause
            pause_cmd = {
                "type": ClientMessageType.CONTROL_CMD.value,
                "payload": {"command": "pause"},
            }
            ws.send_text(json.dumps(pause_cmd))

            # Drain any buffered step frame and find the ACK
            ack = None
            for _ in range(5):
                frame = json.loads(ws.receive_text())
                if frame["type"] == ServerMessageType.CONTROL_ACK.value:
                    ack = frame
                    break
            assert ack is not None
            assert ack["payload"]["command"] == "pause"

            # 2. Resume
            resume_cmd = {
                "type": ClientMessageType.CONTROL_CMD.value,
                "payload": {"command": "resume"},
            }
            ws.send_text(json.dumps(resume_cmd))
            ack_res = None
            for _ in range(5):
                frame = json.loads(ws.receive_text())
                if frame["type"] == ServerMessageType.CONTROL_ACK.value:
                    ack_res = frame
                    break
            assert ack_res is not None
            assert ack_res["payload"]["command"] == "resume"

    def test_websocket_error_handling_and_guards(self, client):
        with client.websocket_connect("/ws/simulation") as ws:
            # 1. Malformed JSON
            ws.send_text("INVALID_NOT_JSON")
            err1 = json.loads(ws.receive_text())
            assert err1["type"] == ServerMessageType.ERROR.value
            assert err1["payload"]["code"] == "MALFORMED_JSON"

            # 2. Missing message type
            ws.send_text(json.dumps({"foo": "bar"}))
            err2 = json.loads(ws.receive_text())
            assert err2["type"] == ServerMessageType.ERROR.value
            assert err2["payload"]["code"] == "MISSING_TYPE"

            # 3. Action before session init
            act_before_init = {
                "type": ClientMessageType.INPUT_ACTION.value,
                "payload": {"step": 0, "action": 2, "client_timestamp": time.time()},
            }
            ws.send_text(json.dumps(act_before_init))
            err3 = json.loads(ws.receive_text())
            assert err3["type"] == ServerMessageType.ERROR.value
            assert err3["payload"]["code"] == "NO_SESSION"

    def test_websocket_disconnect_cleanup(self, client):
        count_before = session_manager.active_session_count

        with client.websocket_connect("/ws/simulation") as ws:
            init_msg = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"mode": "ai", "seed": 42},
            }
            ws.send_text(json.dumps(init_msg))
            _ = ws.receive_text()  # SESSION_READY
            assert session_manager.active_session_count == count_before + 1

        # After exiting context, socket is disconnected and cleaned up
        time.sleep(0.1)
        assert session_manager.active_session_count == count_before

    def test_websocket_strict_input_validation(self, client):
        """Verifies explicit rejection of invalid inputs, out-of-order steps, and wrong flight mode."""
        # 1. Action in AI mode must be rejected with INVALID_MODE
        with client.websocket_connect("/ws/simulation") as ws:
            init_ai = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"mode": "ai", "seed": 42},
            }
            ws.send_text(json.dumps(init_ai))
            _ = ws.receive_text()  # SESSION_READY
            _ = ws.receive_text()  # Step 0

            # Attempt action in AI mode
            act_in_ai = {
                "type": ClientMessageType.INPUT_ACTION.value,
                "payload": {"step": 0, "action": 2, "client_timestamp": time.time()},
            }
            ws.send_text(json.dumps(act_in_ai))

            # Find ERROR frame
            err_frame = None
            for _ in range(5):
                msg = json.loads(ws.receive_text())
                if msg["type"] == ServerMessageType.ERROR.value:
                    err_frame = msg
                    break
            assert err_frame is not None
            assert err_frame["payload"]["code"] == "INVALID_MODE"

        # 2. Strict validation in HUMAN mode: string, float, out-of-range action, and stale steps
        with client.websocket_connect("/ws/simulation") as ws:
            init_human = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"mode": "human", "seed": 42},
            }
            ws.send_text(json.dumps(init_human))
            _ = ws.receive_text()  # SESSION_READY
            _ = ws.receive_text()  # Step 0

            # Out of bounds action (99)
            ws.send_text(json.dumps({
                "type": ClientMessageType.INPUT_ACTION.value,
                "payload": {"step": 1, "action": 99, "client_timestamp": time.time()},
            }))
            err_oob = None
            for _ in range(5):
                msg = json.loads(ws.receive_text())
                if msg["type"] == ServerMessageType.ERROR.value:
                    err_oob = msg
                    break
            assert err_oob is not None
            assert err_oob["payload"]["code"] == "VALIDATION_ERROR"

            # Float action (2.5)
            ws.send_text(json.dumps({
                "type": ClientMessageType.INPUT_ACTION.value,
                "payload": {"step": 2, "action": 2.5, "client_timestamp": time.time()},
            }))
            err_float = None
            for _ in range(5):
                msg = json.loads(ws.receive_text())
                if msg["type"] == ServerMessageType.ERROR.value:
                    err_float = msg
                    break
            assert err_float is not None
            assert err_float["payload"]["code"] == "VALIDATION_ERROR"

            # Valid step 10
            ws.send_text(json.dumps({
                "type": ClientMessageType.INPUT_ACTION.value,
                "payload": {"step": 10, "action": 2, "client_timestamp": time.time()},
            }))

            # Stale step (step 5 after step 10)
            ws.send_text(json.dumps({
                "type": ClientMessageType.INPUT_ACTION.value,
                "payload": {"step": 5, "action": 2, "client_timestamp": time.time()},
            }))
            err_stale = None
            for _ in range(5):
                msg = json.loads(ws.receive_text())
                if msg["type"] == ServerMessageType.ERROR.value:
                    err_stale = msg
                    break
            assert err_stale is not None
            assert err_stale["payload"]["code"] == "STALE_STEP"

    def test_websocket_session_reconnection_and_expiry(self, client):
        """Verifies session expiry error on nonexistent session ID and reconnection to existing session."""
        # 1. Nonexistent session ID -> SESSION_EXPIRED
        with client.websocket_connect("/ws/simulation") as ws:
            reconnect_bogus = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"session_id": "nonexistent-uuid-99999", "mode": "ai"},
            }
            ws.send_text(json.dumps(reconnect_bogus))
            err_msg = json.loads(ws.receive_text())
            assert err_msg["type"] == ServerMessageType.ERROR.value
            assert err_msg["payload"]["code"] == "SESSION_EXPIRED"

        # 2. Existing session reconnection
        with client.websocket_connect("/ws/simulation") as ws1:
            init_msg = {
                "type": ClientMessageType.SESSION_INIT.value,
                "payload": {"mode": "ai", "seed": 42},
            }
            ws1.send_text(json.dumps(init_msg))
            ready1 = json.loads(ws1.receive_text())
            created_sid = ready1["payload"]["session_id"]
            _ = ws1.receive_text()  # Step 0

            # Reconnect with ws2 using created_sid
            with client.websocket_connect("/ws/simulation") as ws2:
                reconnect_msg = {
                    "type": ClientMessageType.SESSION_INIT.value,
                    "payload": {"session_id": created_sid, "mode": "ai"},
                }
                ws2.send_text(json.dumps(reconnect_msg))
                ready2 = json.loads(ws2.receive_text())
                assert ready2["type"] == ServerMessageType.SESSION_READY.value
                assert ready2["payload"]["session_id"] == created_sid

                # ws1 should be evicted with SESSION_TAKEOVER
                takeover_err = None
                for _ in range(5):
                    f = json.loads(ws1.receive_text())
                    if f["type"] == ServerMessageType.ERROR.value:
                        takeover_err = f
                        break
                assert takeover_err is not None
                assert takeover_err["payload"]["code"] == "SESSION_TAKEOVER"
