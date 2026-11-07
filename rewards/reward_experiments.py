"""Reward experiment configurations and comparison registry."""

from typing import Callable, Dict
import gymnasium as gym
from rewards.baseline import BaselineRewardWrapper
from rewards.shaped_reward import ShapedRocketRewardWrapper


REWARD_STRATEGIES: Dict[str, Callable[[gym.Env], gym.Env]] = {
    "baseline": lambda env: BaselineRewardWrapper(env),
    "dense_shaped": lambda env: ShapedRocketRewardWrapper(
        env, dist_coef=1.2, vel_coef=0.8, angle_coef=1.5, fuel_coef=0.05
    ),
    "fuel_efficient": lambda env: ShapedRocketRewardWrapper(
        env, dist_coef=1.0, vel_coef=0.5, angle_coef=1.0, fuel_coef=0.25
    ),
}


def get_reward_wrapper(name: str) -> Callable[[gym.Env], gym.Env]:
    """Retrieves reward wrapper factory by strategy name."""
    if name not in REWARD_STRATEGIES:
        raise ValueError(f"Unknown reward strategy: '{name}'. Available: {list(REWARD_STRATEGIES.keys())}")
    return REWARD_STRATEGIES[name]
