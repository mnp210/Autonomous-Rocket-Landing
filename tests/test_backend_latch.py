"""Unit tests for TerminalStateLatch contact classification, bounce handling, and shutdown."""

import numpy as np
import pytest

from backend.latch import TerminalStateLatch


class TestTerminalStateLatch:
    """Verifies contact state machine, bounce recovery, and terminal propulsion cutoff."""

    def test_airborne_initial_state(self):
        latch = TerminalStateLatch()
        assert not latch.is_latched
        assert latch.touchdown_phase == "AIRBORNE"
        assert latch.contact_type == "NONE"
        assert latch.first_contact is None

    def test_single_leg_unstable_contact_does_not_latch(self):
        """Single leg contact with lateral drift or tilt must allow active recovery."""
        latch = TerminalStateLatch()
        # obs: [x, y, vx, vy, theta, ang_vel, left_contact, right_contact]
        obs = np.array([0.0, 0.05, 0.1, -0.4, 0.15, 0.0, 1.0, 0.0], dtype=np.float32)

        is_latched = latch.check_and_update(obs, terminated=False, truncated=False, step=10)

        assert not is_latched, "Unstable single-leg contact must not prematurely latch"
        assert latch.touchdown_phase == "UNSTABLE_CONTACT"
        assert latch.contact_type == "SINGLE_LEFT"
        assert latch.first_contact is not None
        assert latch.first_contact.step == 10
        # Propulsion actions must NOT be filtered/zeroed
        assert latch.filter_action(2) == 2
        assert latch.filter_action(1) == 1

    def test_contact_followed_by_bounce(self):
        """Lander touches pad, rebounds back airborne (legs lose contact), must not latch."""
        latch = TerminalStateLatch()
        # Step 1: initial touch
        obs_touch = np.array([0.0, 0.04, 0.0, -0.2, 0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        latch.check_and_update(obs_touch, terminated=False, truncated=False, step=50)

        # Step 2: rebound into air (both legs false)
        obs_air = np.array([0.0, 0.10, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        is_latched = latch.check_and_update(obs_air, terminated=False, truncated=False, step=51)

        assert not is_latched
        assert latch.touchdown_phase == "BOUNCE"
        assert latch.contact_type == "NONE"
        assert latch.filter_action(2) == 2, "Action must not be suppressed during bounce recovery"

    def test_stable_dual_leg_touchdown_latches(self):
        """Dual leg contact at low velocity and pad altitude must latch and cut thrust."""
        latch = TerminalStateLatch()
        obs_settled = np.array([0.02, 0.01, 0.02, -0.05, 0.01, 0.0, 1.0, 1.0], dtype=np.float32)

        is_latched = latch.check_and_update(
            obs_settled, terminated=False, truncated=False, step=120, altitude=0.01
        )

        assert is_latched
        assert latch.latch_reason == "TOUCHDOWN_SETTLED"
        assert latch.touchdown_phase == "SETTLED_TOUCHDOWN"
        assert latch.filter_action(2) == 0, "Main engine must be zeroed once latched"
        assert latch.filter_action(1) == 0, "RCS must be zeroed once latched"
        assert latch.filter_action(3) == 0, "RCS must be zeroed once latched"

    def test_environment_termination_crash(self):
        """Terminal crash must engage latch immediately and identify CRASH."""
        latch = TerminalStateLatch()
        obs_crash = np.array([1.2, 0.0, 5.0, -10.0, 1.5, 2.0, 0.0, 0.0], dtype=np.float32)

        is_latched = latch.check_and_update(obs_crash, terminated=True, truncated=False, step=45)

        assert is_latched
        assert latch.latch_reason == "ENVIRONMENT_TERMINATION"
        assert latch.touchdown_phase == "CRASH"
        assert latch.filter_action(2) == 0

    def test_environment_truncation_timeout(self):
        """Environment time limit truncation must engage latch and set TIMEOUT."""
        latch = TerminalStateLatch()
        obs_timeout = np.array([0.1, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        is_latched = latch.check_and_update(obs_timeout, terminated=False, truncated=True, step=1000)

        assert is_latched
        assert latch.latch_reason == "ENVIRONMENT_TRUNCATION"
        assert latch.touchdown_phase == "TIMEOUT"
        assert latch.filter_action(2) == 0
