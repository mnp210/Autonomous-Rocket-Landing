"""Unit tests for pure mathematical reward shaping functions and potential calculations."""

import numpy as np
import pytest

from rewards.reward_config import (
    EnergyPenalties,
    PotentialWeights,
    RewardConfig,
    RewardStrategy,
    StateNormalizers,
)
from rewards.reward_functions import (
    compute_energy_penalty,
    compute_normalized_components,
    compute_potential,
    compute_potential_shaping,
)


class TestRewardFunctions:
    """Test suite for mathematical potential and reward functions."""

    @pytest.fixture
    def default_weights(self):
        return PotentialWeights()

    @pytest.fixture
    def default_normalizers(self):
        return StateNormalizers()

    @pytest.fixture
    def default_penalties(self):
        return EnergyPenalties()

    def test_ideal_touchdown_potential_maximum(self, default_weights, default_normalizers):
        """At ideal landing (centered, stationary, upright, both legs grounded), potential is maximal."""
        # [x, y, vx, vy, theta, theta_dot, left_contact, right_contact]
        ideal_state = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0], dtype=np.float32)
        phi_ideal = compute_potential(ideal_state, default_weights, default_normalizers)

        # Dist=0, Vel=0, Tilt=0, Contacts=2 => phi = 0 + 2*w_legs = 2.0
        assert pytest.approx(phi_ideal, 1e-4) == 2.0 * default_weights.leg_contact

    def test_potential_decreases_with_distance(self, default_weights, default_normalizers):
        """Moving further horizontally from landing pad strictly decreases potential."""
        state_close = np.array([0.1, 0.5, 0.0, -0.2, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        state_far = np.array([1.2, 0.5, 0.0, -0.2, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        phi_close = compute_potential(state_close, default_weights, default_normalizers)
        phi_far = compute_potential(state_far, default_weights, default_normalizers)

        assert phi_close > phi_far

    def test_potential_decreases_with_extreme_velocity(self, default_weights, default_normalizers):
        """High descent speed or lateral velocity severely penalizes potential."""
        slow_state = np.array([0.0, 0.5, 0.05, -0.1, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        fast_state = np.array([0.0, 0.5, 2.5, -4.5, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        phi_slow = compute_potential(slow_state, default_weights, default_normalizers)
        phi_fast = compute_potential(fast_state, default_weights, default_normalizers)

        assert phi_slow > phi_fast

    def test_potential_decreases_with_extreme_tilt(self, default_weights, default_normalizers):
        """Excessive tilt angle or spin rate penalizes potential."""
        upright_state = np.array([0.0, 0.5, 0.0, 0.0, 0.01, 0.01, 0.0, 0.0], dtype=np.float32)
        tilted_state = np.array([0.0, 0.5, 0.0, 0.0, 1.2, 2.5, 0.0, 0.0], dtype=np.float32)

        phi_upright = compute_potential(upright_state, default_weights, default_normalizers)
        phi_tilted = compute_potential(tilted_state, default_weights, default_normalizers)

        assert phi_upright > phi_tilted

    def test_pbrs_telescoping_property(self):
        """Sum of potential differences over trajectory s_0 -> s_1 -> s_2 equals gamma^2*Phi(s_2) - Phi(s_0)."""
        gamma = 0.99
        phi_0 = -2.5
        phi_1 = -1.8
        phi_2 = 1.5

        f_01 = compute_potential_shaping(phi_0, phi_1, gamma=gamma, terminated=False)
        f_12 = compute_potential_shaping(phi_1, phi_2, gamma=gamma, terminated=False)

        # Telescoping sum with discounting: f_01 + gamma * f_12
        total_discounted_shaping = f_01 + gamma * f_12
        expected = (gamma**2 * phi_2) - phi_0
        assert pytest.approx(total_discounted_shaping, 1e-4) == expected

    def test_terminal_state_handling(self):
        """When terminated with zero_terminal_potential=True, effective phi_next is zero."""
        gamma = 0.99
        phi_curr = -1.2
        phi_next_arbitrary = 10.0

        # Terminated transition: F = gamma * 0.0 - phi_curr = -phi_curr
        f_term = compute_potential_shaping(
            phi_current=phi_curr,
            phi_next=phi_next_arbitrary,
            gamma=gamma,
            terminated=True,
            zero_terminal_potential=True,
        )
        assert pytest.approx(f_term, 1e-4) == -phi_curr

        # Non-terminal transition: F = gamma * phi_next - phi_curr
        f_non_term = compute_potential_shaping(
            phi_current=phi_curr,
            phi_next=phi_next_arbitrary,
            gamma=gamma,
            terminated=False,
            zero_terminal_potential=True,
        )
        assert pytest.approx(f_non_term, 1e-4) == (gamma * phi_next_arbitrary) - phi_curr

    def test_energy_penalties(self, default_penalties):
        """Ensures idle thruster has 0 cost, while main engine and side thrusters apply calibrated penalties."""
        # Action 0: No-op
        assert compute_energy_penalty(0, prev_action=None, penalties=default_penalties) == 0.0
        assert compute_energy_penalty(0, prev_action=0, penalties=default_penalties) == 0.0

        # Action 2: Main engine
        main_cost = compute_energy_penalty(2, prev_action=2, penalties=default_penalties)
        assert pytest.approx(main_cost, 1e-4) == default_penalties.main_engine

        # Action 1 & 3: Side thrusters
        side_cost_1 = compute_energy_penalty(1, prev_action=1, penalties=default_penalties)
        side_cost_3 = compute_energy_penalty(3, prev_action=3, penalties=default_penalties)
        assert pytest.approx(side_cost_1, 1e-4) == default_penalties.side_thruster
        assert pytest.approx(side_cost_3, 1e-4) == default_penalties.side_thruster

        # Action switching adds chattering penalty
        switch_cost = compute_energy_penalty(2, prev_action=1, penalties=default_penalties)
        expected_switch = default_penalties.main_engine + default_penalties.control_switch
        assert pytest.approx(switch_cost, 1e-4) == expected_switch

    def test_numerical_stability_edge_cases(self, default_weights, default_normalizers):
        """Verifies potential computation remains finite under extreme / pathological physical states."""
        # Extreme crash / supersonic impact speed
        extreme_state = np.array([100.0, -10.0, 50.0, -50.0, 30.0, 100.0, 0.0, 0.0], dtype=np.float32)
        phi_extreme = compute_potential(extreme_state, default_weights, default_normalizers)
        assert np.isfinite(phi_extreme)
        assert phi_extreme < -50.0
