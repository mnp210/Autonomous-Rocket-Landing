"""Pure mathematical reward shaping functions and potential calculations.

Implements Potential-Based Reward Shaping (PBRS) under the Ng, Harada, & Russell (1999)
formulation to preserve optimal policy invariance:
    F(s, s') = gamma * Phi(s') - Phi(s)

Includes independent energy expenditure proxies for actuator thriftiness.
"""

from typing import Dict, Optional, Tuple, Union
import numpy as np

from rewards.reward_config import RewardConfig, StateNormalizers, PotentialWeights, EnergyPenalties


def compute_normalized_components(
    obs: np.ndarray,
    normalizers: StateNormalizers,
) -> Dict[str, float]:
    """Computes normalized kinematic components from an 8-dimensional observation vector.

    Observation schema:
        [x, y, vx, vy, theta, theta_dot, left_leg_contact, right_leg_contact]

    Args:
        obs: NumPy array of shape (8,).
        normalizers: Normalization scale factors.

    Returns:
        Dictionary of normalized terms and derived metrics.
    """
    x = float(obs[0])
    y = float(obs[1])
    vx = float(obs[2])
    vy = float(obs[3])
    theta = float(obs[4])
    theta_dot = float(obs[5])
    left_contact = float(obs[6])
    right_contact = float(obs[7])

    norm_x = x / max(1e-4, normalizers.x)
    norm_y = y / max(1e-4, normalizers.y)
    norm_vx = vx / max(1e-4, normalizers.vx)
    norm_vy = vy / max(1e-4, normalizers.vy)
    norm_theta = theta / max(1e-4, normalizers.theta)
    norm_theta_dot = theta_dot / max(1e-4, normalizers.theta_dot)

    # Euclidean distance from landing pad (0, 0)
    norm_dist = np.sqrt(norm_x**2 + norm_y**2)

    # Linear velocity magnitude
    norm_speed = np.sqrt(norm_vx**2 + norm_vy**2)

    # Angular displacement & rotational velocity penalty
    norm_tilt = abs(norm_theta)
    norm_spin = abs(norm_theta_dot)

    return {
        "norm_dist": float(norm_dist),
        "norm_speed": float(norm_speed),
        "norm_tilt": float(norm_tilt),
        "norm_spin": float(norm_spin),
        "contact_count": float(left_contact + right_contact),
    }


def compute_potential(
    obs: np.ndarray,
    weights: PotentialWeights,
    normalizers: StateNormalizers,
) -> float:
    """Calculates scalar potential Phi(s) for a given kinematic state.

    Higher potential corresponds to states closer to pad, upright, with low velocity
    and grounded landing legs. At ideal touchdown, Phi(s) achieves its peak value.

    Args:
        obs: 8-dimensional state vector.
        weights: Potential term weights.
        normalizers: State normalization divisors.

    Returns:
        Scalar potential Phi(s).
    """
    comps = compute_normalized_components(obs, normalizers)

    # Negative costs for deviation from ideal landing state
    pos_cost = weights.distance * comps["norm_dist"]
    vel_cost = weights.velocity * comps["norm_speed"]
    angle_cost = weights.angle * comps["norm_tilt"]
    spin_cost = weights.angular_velocity * comps["norm_spin"]

    # Positive bonus for confirmed ground contact
    contact_bonus = weights.leg_contact * comps["contact_count"]

    phi = -(pos_cost + vel_cost + angle_cost + spin_cost) + contact_bonus
    return float(phi)


def compute_potential_shaping(
    phi_current: float,
    phi_next: float,
    gamma: float = 0.99,
    terminated: bool = False,
    zero_terminal_potential: bool = True,
    shaping_scale: float = 1.0,
) -> float:
    """Computes the potential-based shaping term F(s, s') = gamma * Phi(s') - Phi(s).

    Handles terminal boundary conditions consistently:
    If zero_terminal_potential is True and terminated is True, Phi(s') is evaluated as 0.0,
    preventing spurious potential windfalls upon terminal crash.

    Args:
        phi_current: Potential of current state Phi(s).
        phi_next: Potential of subsequent state Phi(s').
        gamma: MDP discount factor.
        terminated: Whether the transition reached a terminal absorbing state.
        zero_terminal_potential: Enforce Phi(s_term) = 0.
        shaping_scale: Global scaling multiplier.

    Returns:
        Shaping reward term F(s, s').
    """
    effective_phi_next = 0.0 if (terminated and zero_terminal_potential) else phi_next
    shaping = (gamma * effective_phi_next) - phi_current
    return float(shaping * shaping_scale)


def compute_energy_penalty(
    action: int,
    prev_action: Optional[int],
    penalties: EnergyPenalties,
) -> float:
    """Computes actuator energy consumption penalty for discrete thruster controls.

    Actions:
        0: No-op (idle, zero cost)
        1: Left orientation thruster
        2: Main central rocket engine
        3: Right orientation thruster

    Also applies a switching penalty to discourage high-frequency control chattering.

    Args:
        action: Active discrete action ID (0, 1, 2, or 3).
        prev_action: Preceding action ID from previous timestep, if any.
        penalties: Penalty weights for main engine, side thrusters, and chattering.

    Returns:
        Non-negative energy cost to be subtracted from reward.
    """
    cost = 0.0

    if action == 2:
        cost += penalties.main_engine
    elif action in (1, 3):
        cost += penalties.side_thruster

    # Control chatter penalty
    if prev_action is not None and action != prev_action and action != 0:
        cost += penalties.control_switch

    return float(cost)
