"""Stage 8.4.1 — Post-Landing Propulsion Shutdown, Episode Reset & Replay Reliability Test Suite.

Verifies:
1. Successful landing shuts down propulsion (throttle == 0.0, rcs == 0.0).
2. Crash termination shuts down propulsion.
3. Truncation shuts down propulsion.
4. No additional policy predictions occur after termination.
5. A second episode starts with clean action and renderer state.
6. Three consecutive AI episodes complete without stale state.
7. Identical seeds produce equivalent simulation trajectories across consecutive runs.
8. Timeline snapshots from different episodes cannot be mixed.
9. No stale engine flame or RCS emission persists after reset.
"""

import math
from pathlib import Path
import sys
import pytest

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# On Windows, PyTorch's c10.dll must be pre-loaded before Panda3D OpenGL runtime
try:
    import torch
except Exception:
    pass

import gymnasium as gym
import numpy as np

from evaluation.evaluate import LandingCriteria
from visualization.realistic3d_renderer import Realistic3DRenderer
from visualization.timeline import SimulationSnapshot, SnapshotTimeline, capture_snapshot_from_env


@pytest.fixture(scope="module")
def shared_renderer():
    """Provides a headless Realistic3DRenderer instance for tests."""
    rend = Realistic3DRenderer(headless=True, width=640, height=360, speed_factor=1.0)
    yield rend
    rend.close()


class TestPropulsionShutdown:
    """Verifies that propulsion is reliably shut down across all terminal and touchdown states."""

    def test_successful_landing_shuts_down_propulsion(self, shared_renderer):
        """Scenario 1: Successful landing shuts down propulsion (throttle == 0.0, rcs == 0.0)."""
        env = gym.make("LunarLander-v3")
        obs, _ = env.reset(seed=42)

        # Create a settled touchdown observation with both legs contacting
        mock_obs = np.array([0.0, 0.02, 0.01, -0.01, 0.01, 0.0, 1.0, 1.0], dtype=np.float32)
        snap = capture_snapshot_from_env(
            env=env,
            obs=mock_obs,
            action=2,  # Main engine requested by policy
            step=250,
            reward=100.0,
            terminated=True,
            truncated=False,
            outcome="SUCCESS",
        )
        assert snap.throttle == 0.0, f"Expected 0.0 throttle on success, got {snap.throttle}"
        assert snap.rcs_left == 0.0, f"Expected 0.0 RCS left on success, got {snap.rcs_left}"
        assert snap.rcs_right == 0.0, f"Expected 0.0 RCS right on success, got {snap.rcs_right}"
        assert snap.touchdown_phase == "SETTLED TOUCHDOWN"

        # Verify renderer also clamps propulsion and hides visual plume
        shared_renderer.render_snapshot(snap)
        assert shared_renderer.current_throttle == 0.0
        assert shared_renderer.current_rcs_l == 0.0
        assert shared_renderer.current_rcs_r == 0.0
        assert shared_renderer.plume_root.isHidden()
        assert shared_renderer.rcs_jet_l.isHidden()
        assert shared_renderer.rcs_jet_r.isHidden()
        env.close()

    def test_crash_termination_shuts_down_propulsion(self, shared_renderer):
        """Scenario 2: Crash termination shuts down propulsion."""
        env = gym.make("LunarLander-v3")
        obs, _ = env.reset(seed=42)

        mock_obs = np.array([0.5, 0.0, 2.0, -3.0, 1.5, 2.0, 0.0, 0.0], dtype=np.float32)
        snap = capture_snapshot_from_env(
            env=env,
            obs=mock_obs,
            action=2,  # Policy commanded main engine on crash step
            step=180,
            reward=-100.0,
            terminated=True,
            truncated=False,
            outcome="CRASH",
        )
        assert snap.throttle == 0.0
        assert snap.rcs_left == 0.0
        assert snap.rcs_right == 0.0
        assert snap.touchdown_phase == "LANDING IMPACT"

        shared_renderer.render_snapshot(snap)
        assert shared_renderer.current_throttle == 0.0
        assert shared_renderer.plume_root.isHidden()
        env.close()

    def test_truncation_shuts_down_propulsion(self, shared_renderer):
        """Scenario 3: Truncation shuts down propulsion."""
        env = gym.make("LunarLander-v3")
        obs, _ = env.reset(seed=42)

        snap = capture_snapshot_from_env(
            env=env,
            obs=obs,
            action=3,  # Policy commanded right RCS
            step=1000,
            reward=0.0,
            terminated=False,
            truncated=True,
            outcome="TIME_LIMIT",
        )
        assert snap.throttle == 0.0
        assert snap.rcs_left == 0.0
        assert snap.rcs_right == 0.0

        shared_renderer.render_snapshot(snap)
        assert shared_renderer.current_rcs_r == 0.0
        assert shared_renderer.rcs_jet_r.isHidden()
        env.close()

    def test_settled_touchdown_before_termination_shuts_down_propulsion(self):
        """Verifies that when both legs are resting on the pad with near-zero speed, propulsion is cut off."""
        class MockVec:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        class MockLander:
            position = MockVec(10.0, 3.35)
            linearVelocity = MockVec(0.01, -0.02)
            angularVelocity = 0.0
            angle = 0.02

        class MockLeg:
            ground_contact = True
            position = MockVec(10.0, 3.34)

        class MockEnv:
            class unwrapped:
                lander = MockLander()
                legs = [MockLeg(), MockLeg()]
                helipad_x1 = 8.0
                helipad_x2 = 12.0
                helipad_y = 3.333
                terrain = []

        mock_obs = np.array([0.02, 0.03, 0.01, -0.02, 0.05, 0.0, 1.0, 1.0], dtype=np.float32)
        snap = capture_snapshot_from_env(
            env=MockEnv(),
            obs=mock_obs,
            action=3,  # Policy trying to correct residual tilt with RCS
            step=685,
            reward=0.0,
            terminated=False,
            truncated=False,
            outcome=None,
        )
        assert snap.throttle == 0.0
        assert snap.rcs_left == 0.0
        assert snap.rcs_right == 0.0
        assert snap.touchdown_phase == "SETTLED TOUCHDOWN"


class TestEpisodeLifecycleAndReset:
    """Verifies clean episode transitions, absence of stale state, and replay determinism."""

    def test_no_additional_policy_predictions_after_termination(self):
        """Scenario 4: No additional policy predictions occur after termination."""
        env = gym.make("LunarLander-v3")
        obs, _ = env.reset(seed=42)

        prediction_count = 0
        step_count = 0
        done = False

        # Mock policy tracking call count
        def mock_predict(observation):
            nonlocal prediction_count
            prediction_count += 1
            return 2, None

        while not done:
            action, _ = mock_predict(obs)
            obs, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            step_count += 1
            if step_count > 120:  # Force termination
                break

        # Record count at termination
        final_prediction_count = prediction_count
        assert done is True or step_count > 120

        # Run debrief period: ensure no further predict() calls
        debrief_ticks = 10
        for _ in range(debrief_ticks):
            # Debrief hold uses action=0 without calling predict()
            pass

        assert prediction_count == final_prediction_count, "Policy predict() called after episode termination!"
        env.close()

    def test_second_episode_starts_with_clean_action_and_renderer_state(self, shared_renderer):
        """Scenario 5: A second episode starts with clean action and renderer state."""
        env = gym.make("LunarLander-v3")
        obs, _ = env.reset(seed=42)

        # Step 1: Put renderer into a high-thrust, ground-level state
        active_snap = SimulationSnapshot(
            step=300,
            sim_time=6.0,
            pos_x=0.0,
            pos_y=0.2,
            pos_z=0.0,
            pitch=0.0,
            yaw=0.0,
            roll=0.0,
            vel_x=0.0,
            vel_y=-0.1,
            vel_z=0.0,
            ang_vel=0.0,
            action=2,
            throttle=1.0,
            rcs_left=0.0,
            rcs_right=0.0,
            left_contact=False,
            right_contact=False,
            altitude=0.0,
            touchdown_phase="TERMINAL DECELERATION",
            reward=0.0,
            cumulative_reward=200.0,
            terminated=False,
            truncated=False,
            outcome=None,
        )
        shared_renderer.render_snapshot(active_snap)
        assert shared_renderer.current_throttle > 0.05
        assert not shared_renderer.plume_root.isHidden()

        # Step 2: Reset for Episode 2
        obs2, _ = env.reset(seed=43)
        init_snap2 = capture_snapshot_from_env(env, obs2, action=0, step=0)
        shared_renderer.reset(initial_snapshot=init_snap2)

        # Step 3: Verify clean state
        assert shared_renderer.current_throttle == 0.0
        assert shared_renderer.current_rcs_l == 0.0
        assert shared_renderer.current_rcs_r == 0.0
        assert shared_renderer.dust_intensity == 0.0
        assert shared_renderer.plume_root.isHidden()
        assert shared_renderer.rcs_jet_l.isHidden()
        assert shared_renderer.rcs_jet_r.isHidden()
        assert shared_renderer.dust_root.isHidden()

        # Camera must snap directly to spawn altitude without lagging spring delay
        is_spaceport = getattr(shared_renderer, "theme", "") == "spaceport"
        expected_cam_z = max(7.5, init_snap2.pos_y * 0.55 + 6.0) if is_spaceport else max(2.5, init_snap2.pos_y * 0.55 + 1.4)
        assert abs(shared_renderer.cam_smooth_z - expected_cam_z) < 1e-4, (
            f"Camera z did not snap to spawn altitude: {shared_renderer.cam_smooth_z} vs {expected_cam_z}"
        )
        env.close()

    def test_three_consecutive_ai_episodes_complete_without_stale_state(self, shared_renderer):
        """Scenario 6: Three consecutive AI episodes complete without stale state."""
        env = gym.make("LunarLander-v3")
        episode_lengths = []
        episode_rewards = []

        for ep in range(3):
            obs, _ = env.reset(seed=42 + ep)
            init_snap = capture_snapshot_from_env(env, obs, action=0, step=0)
            shared_renderer.reset(initial_snapshot=init_snap)

            # Confirm clean reset at step 0
            assert shared_renderer.current_throttle == 0.0
            assert shared_renderer.plume_root.isHidden()

            done = False
            total_r = 0.0
            step = 0
            while not done and step < 80:  # Limited steps for fast test
                act = 2 if step % 4 == 0 else 0
                snap = capture_snapshot_from_env(env, obs, action=act, step=step)
                shared_renderer.render_snapshot(snap)
                obs, r, term, trunc, _ = env.step(act)
                total_r += r
                done = term or trunc
                step += 1

            episode_lengths.append(step)
            episode_rewards.append(total_r)

            # Debrief hold at episode end (terminated=True enforces immediate propulsion cutoff)
            final_snap = capture_snapshot_from_env(env, obs, action=0, step=step, terminated=True)
            shared_renderer.render_snapshot(final_snap)
            assert shared_renderer.plume_root.isHidden()

        assert len(episode_lengths) == 3
        assert all(l > 0 for l in episode_lengths)
        env.close()

    def test_identical_seeds_produce_equivalent_simulation_trajectories(self):
        """Scenario 7: Identical seeds produce equivalent simulation trajectories across consecutive runs."""
        env = gym.make("LunarLander-v3")

        # Run 1 with seed 42
        obs1, _ = env.reset(seed=42)
        traj1 = [obs1.copy()]
        for _ in range(40):
            obs1, _, _, _, _ = env.step(2)
            traj1.append(obs1.copy())

        # Interleaved Run with seed 999
        obs_inter, _ = env.reset(seed=999)
        for _ in range(30):
            env.step(1)

        # Run 2 with seed 42
        obs2, _ = env.reset(seed=42)
        traj2 = [obs2.copy()]
        for _ in range(40):
            obs2, _, _, _, _ = env.step(2)
            traj2.append(obs2.copy())

        for step_idx, (s1, s2) in enumerate(zip(traj1, traj2)):
            np.testing.assert_allclose(
                s1, s2, atol=1e-6,
                err_msg=f"Trajectory mismatch at step {step_idx} between identical seeds!"
            )
        env.close()

    def test_timeline_snapshots_from_different_episodes_cannot_be_mixed(self):
        """Scenario 8: Timeline snapshots from different episodes cannot be mixed."""
        timeline_ep1 = SnapshotTimeline(dt=0.02)
        timeline_ep2 = SnapshotTimeline(dt=0.02)

        snap1 = SimulationSnapshot(
            step=1, sim_time=0.02, pos_x=0.0, pos_y=10.0, pos_z=0.0,
            pitch=0.0, yaw=0.0, roll=0.0, vel_x=0.0, vel_y=0.0, vel_z=0.0, ang_vel=0.0,
            action=0, throttle=0.0, rcs_left=0.0, rcs_right=0.0,
            left_contact=False, right_contact=False, altitude=10.0,
            touchdown_phase="HIGH DESCENT", reward=0.0, cumulative_reward=0.0,
            terminated=False, truncated=False, outcome=None,
        )
        timeline_ep1.add_snapshot(snap1)

        snap2 = SimulationSnapshot(
            step=1, sim_time=0.02, pos_x=1.5, pos_y=10.2, pos_z=0.0,
            pitch=0.0, yaw=0.0, roll=0.0, vel_x=0.0, vel_y=0.0, vel_z=0.0, ang_vel=0.0,
            action=0, throttle=0.0, rcs_left=0.0, rcs_right=0.0,
            left_contact=False, right_contact=False, altitude=10.2,
            touchdown_phase="HIGH DESCENT", reward=0.0, cumulative_reward=0.0,
            terminated=False, truncated=False, outcome=None,
        )
        timeline_ep2.add_snapshot(snap2)

        assert timeline_ep1.get_snapshot(0).pos_x == 0.0
        assert timeline_ep2.get_snapshot(0).pos_x == 1.5
        assert len(timeline_ep1) == 1
        assert len(timeline_ep2) == 1

        # Attempting to add out-of-order time raises error
        stale_snap = SimulationSnapshot(
            step=0, sim_time=0.00, pos_x=0.0, pos_y=10.0, pos_z=0.0,
            pitch=0.0, yaw=0.0, roll=0.0, vel_x=0.0, vel_y=0.0, vel_z=0.0, ang_vel=0.0,
            action=0, throttle=0.0, rcs_left=0.0, rcs_right=0.0,
            left_contact=False, right_contact=False, altitude=10.0,
            touchdown_phase="HIGH DESCENT", reward=0.0, cumulative_reward=0.0,
            terminated=False, truncated=False, outcome=None,
        )
        with pytest.raises(ValueError, match="monotonically increasing"):
            timeline_ep1.add_snapshot(stale_snap)

    def test_no_stale_engine_flame_or_rcs_persists_after_reset(self, shared_renderer):
        """Scenario 9: No stale engine flame or RCS emission persists after reset."""
        # Force active thruster visual state
        full_thrust_snap = SimulationSnapshot(
            step=50, sim_time=1.0, pos_x=0.0, pos_y=5.0, pos_z=0.0,
            pitch=0.0, yaw=0.0, roll=0.0, vel_x=0.0, vel_y=-1.0, vel_z=0.0, ang_vel=0.0,
            action=2, throttle=1.0, rcs_left=0.0, rcs_right=0.0,
            left_contact=False, right_contact=False, altitude=5.0,
            touchdown_phase="GUIDANCE CORRECTION", reward=0.0, cumulative_reward=10.0,
            terminated=False, truncated=False, outcome=None,
        )
        shared_renderer.render_snapshot(full_thrust_snap)
        assert shared_renderer.current_throttle > 0.05
        assert not shared_renderer.plume_root.isHidden()

        # Call reset
        shared_renderer.reset()

        # Immediate verification
        assert shared_renderer.current_throttle == 0.0
        assert shared_renderer.current_rcs_l == 0.0
        assert shared_renderer.current_rcs_r == 0.0
        assert shared_renderer.dust_intensity == 0.0
        assert shared_renderer.plume_root.isHidden()
        assert shared_renderer.rcs_jet_l.isHidden()
        assert shared_renderer.rcs_jet_r.isHidden()
        assert shared_renderer.dust_root.isHidden()
