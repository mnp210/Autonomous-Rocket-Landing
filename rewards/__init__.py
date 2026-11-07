"""Reward shaping module for Autonomous Rocket Landing."""

from rewards.reward_config import (
    RewardConfig,
    RewardStrategy,
    PotentialWeights,
    StateNormalizers,
    EnergyPenalties,
    load_reward_config,
)
from rewards.reward_functions import (
    compute_potential,
    compute_potential_shaping,
    compute_energy_penalty,
    compute_normalized_components,
)
from rewards.reward_wrapper import RocketRewardShapingWrapper

__all__ = [
    "RewardConfig",
    "RewardStrategy",
    "PotentialWeights",
    "StateNormalizers",
    "EnergyPenalties",
    "load_reward_config",
    "compute_potential",
    "compute_potential_shaping",
    "compute_energy_penalty",
    "compute_normalized_components",
    "RocketRewardShapingWrapper",
]
