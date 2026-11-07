"""Performance metrics: landing success rate, fuel efficiency, touchdown tilt, impact velocity."""

from typing import Any, Dict, List
import numpy as np


def compute_flight_metrics(trajectories: List[List[Dict[str, Any]]]) -> Dict[str, float]:
    """Computes aggregate landing statistics from evaluated flight rollouts.

    Args:
        trajectories: List of episodes containing state, action, and reward steps.

    Returns:
        Dictionary of summary statistics.
    """
    total_episodes = len(trajectories)
    if total_episodes == 0:
        return {}

    total_rewards = []
    final_positions = []
    final_vertical_velocities = []
    final_angles = []
    fuel_consumptions = []
    successes = 0

    for ep in trajectories:
        ep_rewards = sum(step["reward"] for step in ep)
        total_rewards.append(ep_rewards)

        last_state = ep[-1]["state"]
        # obs: [x, y, vx, vy, angle, angular_vel, left_leg, right_leg]
        x, y, vx, vy, angle, _ = last_state[:6]
        left_leg, right_leg = last_state[6], last_state[7]

        final_positions.append(abs(x))
        final_vertical_velocities.append(abs(vy))
        final_angles.append(abs(angle))

        actions = np.array([step["action"] for step in ep])
        fuel_consumptions.append(np.sum(np.square(actions)))

        # Landed successfully: reward >= 200 or legs touching pad with low tilt & velocity
        if ep_rewards >= 200.0 or (left_leg == 1.0 and right_leg == 1.0 and abs(x) < 0.2 and abs(vy) < 0.2):
            successes += 1

    return {
        "success_rate": successes / total_episodes,
        "mean_reward": float(np.mean(total_rewards)),
        "std_reward": float(np.std(total_rewards)),
        "mean_landing_offset": float(np.mean(final_positions)),
        "mean_touchdown_velocity": float(np.mean(final_vertical_velocities)),
        "mean_touchdown_angle_rad": float(np.mean(final_angles)),
        "mean_fuel_consumption": float(np.mean(fuel_consumptions)),
    }
