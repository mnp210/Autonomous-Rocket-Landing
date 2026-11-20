"""Unit and integration tests for backend SimulationSession and headless execution."""

import time
import numpy as np
import pytest
from stable_baselines3 import PPO

from backend.config import DEFAULT_MODEL_PATH
from backend.schemas import FlightMode, PolicyMode, SimulationSnapshotPayload, StormSeverity
from backend.simulation_engine import SimulationSession


@pytest.fixture(scope="module")
def ppo_model():
    """Loads the trained benchmark model for testing."""
    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip(f"Benchmark model not found at {DEFAULT_MODEL_PATH}")
    return PPO.load(str(DEFAULT_MODEL_PATH))


class TestBackendSimulation:
    """Tests the headless SimulationSession engine."""

    def test_environment_creation_and_cleanup(self):
        session = SimulationSession(mode=FlightMode.AI, seed=42)
        assert session.env is not None
        assert session.step_count == 0
        assert session.sim_time == 0.0

        # Close session
        session.close()
        assert session.env is None

    def test_ai_inference_with_real_trained_model(self, ppo_model):
        session = SimulationSession(mode=FlightMode.AI, seed=42)
        snap = session.step_ai(ppo_model)

        assert isinstance(snap, SimulationSnapshotPayload)
        assert snap.lifecycle.step == 1
        assert snap.lifecycle.sim_time == 0.02
        assert snap.propulsion.action in (0, 1, 2, 3)
        assert not np.isnan(snap.kinematics.pos_x)
        assert not np.isnan(snap.kinematics.pos_y)

        session.close()

    def test_human_action_validation(self):
        session = SimulationSession(mode=FlightMode.HUMAN, seed=42)

        # Valid action (0, 1, 2, 3)
        for act in (0, 1, 2, 3):
            snap = session.step_human(act)
            assert snap.propulsion.action == act

        # Strict validation: Action out of bounds or invalid type must raise ValueError
        with pytest.raises(ValueError, match="Invalid discrete action"):
            session.step_human(99)

        with pytest.raises(ValueError, match="Invalid discrete action"):
            session.step_human(-5)

        with pytest.raises(ValueError, match="Invalid discrete action"):
            session.step_human(2.5)  # float

        with pytest.raises(ValueError, match="Invalid discrete action"):
            session.step_human(True)  # boolean

        with pytest.raises(ValueError, match="Invalid discrete action"):
            session.step_human("2")  # string

        session.close()

    def test_gymnasium_timelimit_truncation(self):
        """Verify that Gymnasium LunarLander-v3 truncates natively at step 1000."""
        session = SimulationSession(mode=FlightMode.HUMAN, seed=42)
        # Advance simulation with coast (action 0) until terminated or truncated
        # To avoid early crash terminating, we check unwrapped spec or advance
        assert hasattr(session.env, "_max_episode_steps")
        assert session.env._max_episode_steps == 1000
        session.close()

    def test_deterministic_same_seed_behavior(self, ppo_model):
        """Two sessions initialized with identical seed must yield identical trajectories."""
        s1 = SimulationSession(mode=FlightMode.AI, policy_mode=PolicyMode.DETERMINISTIC, seed=42)
        s2 = SimulationSession(mode=FlightMode.AI, policy_mode=PolicyMode.DETERMINISTIC, seed=42)

        actions_1, actions_2 = [], []
        positions_1, positions_2 = [], []

        for _ in range(30):
            snap1 = s1.step_ai(ppo_model)
            snap2 = s2.step_ai(ppo_model)

            actions_1.append(snap1.propulsion.action)
            actions_2.append(snap2.propulsion.action)
            positions_1.append((snap1.kinematics.pos_x, snap1.kinematics.pos_y))
            positions_2.append((snap2.kinematics.pos_x, snap2.kinematics.pos_y))

        s1.close()
        s2.close()

        assert actions_1 == actions_2, "Deterministic inference produced divergent actions"
        assert np.allclose(positions_1, positions_2, atol=1e-5), "Deterministic trajectories diverged"

    def test_stochastic_inference_behavior(self, ppo_model):
        """Stochastic sessions with same seed must sample diverse action sequences."""
        s1 = SimulationSession(mode=FlightMode.AI, policy_mode=PolicyMode.STOCHASTIC, seed=42)
        s2 = SimulationSession(mode=FlightMode.AI, policy_mode=PolicyMode.STOCHASTIC, seed=42)

        actions_1, actions_2 = [], []
        for _ in range(50):
            snap1 = s1.step_ai(ppo_model)
            snap2 = s2.step_ai(ppo_model)
            actions_1.append(snap1.propulsion.action)
            actions_2.append(snap2.propulsion.action)

        s1.close()
        s2.close()

        assert actions_1 != actions_2, "Stochastic policy unexpectedly produced identical actions across runs"

    def test_snapshot_schema_serialization(self, ppo_model):
        session = SimulationSession(mode=FlightMode.AI, seed=42)
        snap = session.step_ai(ppo_model)

        json_str = snap.model_dump_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 100

        # Validate round-trip deserialization
        reconstructed = SimulationSnapshotPayload.model_validate_json(json_str)
        assert reconstructed.kinematics.pos_x == snap.kinematics.pos_x
        assert reconstructed.propulsion.action == snap.propulsion.action

        session.close()

    def test_multiple_isolated_sessions(self, ppo_model):
        """Running multiple sessions concurrently must not leak state between them."""
        s_ai = SimulationSession(mode=FlightMode.AI, seed=42)
        s_human = SimulationSession(mode=FlightMode.HUMAN, seed=999)

        snap_ai = s_ai.step_ai(ppo_model)
        snap_human = s_human.step_human(2)

        assert s_ai.session_id != s_human.session_id
        assert s_ai.seed != s_human.seed
        assert snap_ai.kinematics.pos_x != snap_human.kinematics.pos_x

        s_ai.close()
        s_human.close()

    def test_step_latency_performance(self, ppo_model):
        """Measures micro-benchmarks for model inference and physics step latency."""
        session = SimulationSession(mode=FlightMode.AI, seed=42)

        t_infer = []
        t_step = []

        for _ in range(50):
            t0 = time.perf_counter()
            action_pred, _ = ppo_model.predict(session.last_obs, deterministic=True)
            t1 = time.perf_counter()
            t_infer.append(t1 - t0)

            session.step_ai(ppo_model)
            t2 = time.perf_counter()
            t_step.append(t2 - t1)

        session.close()

        mean_infer_ms = np.mean(t_infer) * 1000.0
        mean_step_ms = np.mean(t_step) * 1000.0

        print(f"\n[LATENCY BENCHMARK] PPO Inference: {mean_infer_ms:.3f} ms | Complete Step: {mean_step_ms:.3f} ms")
        assert mean_infer_ms < 2.5, f"Inference exceeded latency threshold: {mean_infer_ms:.2f} ms"
        assert mean_step_ms < 5.0, f"Full step exceeded latency threshold: {mean_step_ms:.2f} ms"
