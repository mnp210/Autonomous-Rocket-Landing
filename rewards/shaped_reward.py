"""Custom reward shaping functions targeting soft touchdown, vertical orientation, and fuel efficiency."""

from typing import Any, Dict, Tuple
import gymnasium as gym
import numpy as np


class ShapedRocketRewardWrapper(gym.Wrapper):
    """Reward wrapper implementing multi-objective shaped rewards for rocket landing.

    Penalizes:
        - Distance from landing pad center
        - High vertical descent velocity near ground
        - Excessive tilt angle and angular velocity
        - Fuel consumption (action magnitude)

    Rewards:
        - Safe leg contact and upright touchdown
        - Controlled hover / descent profile
    """

    def __init__(
        self,
        env: gym.Env,
        dist_coef: float = 1.0,
        vel_coef: float = 0.5,
        angle_coef: float = 1.0,
        fuel_coef: float = 0.1,
    ):
        super().__init__(env)
        self.dist_coef = dist_coef
        self.vel_coef = vel_coef
        self.angle_coef = angle_coef
        self.fuel_coef = fuel_coef

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        obs, original_reward, terminated, truncated, info = self.env.step(action)

        # Parse LunarLander-like observation:
        # [x, y, vx, vy, angle, angular_vel, left_leg_contact, right_leg_contact]
        x, y, vx, vy, angle, angular_vel = obs[0], obs[1], obs[2], obs[3], obs[4], obs[5]

        # Multi-component shaping terms
        distance_penalty = -self.dist_coef * np.sqrt(x**2 + y**2)
        velocity_penalty = -self.vel_coef * (np.sqrt(vx**2 + vy**2))
        angle_penalty = -self.angle_coef * (abs(angle) + 0.5 * abs(angular_vel))
        fuel_penalty = -self.fuel_coef * np.sum(np.square(action))

        shaped_reward = original_reward + distance_penalty + velocity_penalty + angle_penalty + fuel_penalty

        info["reward_components"] = {
            "original": original_reward,
            "distance_penalty": distance_penalty,
            "velocity_penalty": velocity_penalty,
            "angle_penalty": angle_penalty,
            "fuel_penalty": fuel_penalty,
        }

        return obs, float(shaped_reward), terminated, truncated, info
