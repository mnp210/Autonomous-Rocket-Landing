"""Baseline reward wrapper and calculator for standard lunar landing."""

from typing import Any, Dict, Tuple
import gymnasium as gym
import numpy as np


class BaselineRewardWrapper(gym.RewardWrapper):
    """Pass-through or default reward wrapper serving as a baseline benchmark."""

    def __init__(self, env: gym.Env):
        super().__init__(env)

    def reward(self, reward: float) -> float:
        """Returns unmodified environment reward for baseline comparison."""
        return reward
