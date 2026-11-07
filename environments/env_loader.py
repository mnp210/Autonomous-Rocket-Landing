"""Gymnasium LunarLander-v3 environment loader and factory functions.

Ensures deterministic initialization, proper seed handling, and valid wrappers.
Supports optional reward shaping wrappers, domain randomization, and curriculum learning
while preserving full backward compatibility.
"""

from typing import Any, Dict, Optional, Union
import gymnasium as gym

from rewards.reward_config import RewardConfig, load_reward_config
from rewards.reward_wrapper import RocketRewardShapingWrapper
from environments.domain_randomization import (
    DomainRandomizationConfig,
    DomainRandomizationWrapper,
    load_domain_randomization_config,
)
from environments.curriculum import (
    CurriculumConfig,
    CurriculumManager,
    CurriculumEnvWrapper,
    load_curriculum_config,
)


def make_environment(
    env_id: str = "LunarLander-v3",
    continuous: bool = False,
    gravity: float = -10.0,
    enable_wind: bool = False,
    wind_power: float = 15.0,
    turbulence_power: float = 1.5,
    render_mode: Optional[str] = None,
    seed: Optional[int] = None,
    reward_config: Optional[Union[RewardConfig, Dict[str, Any], str]] = None,
    domain_randomization_config: Optional[Union[DomainRandomizationConfig, Dict[str, Any], str]] = None,
    curriculum_manager: Optional[CurriculumManager] = None,
    **kwargs: Any,
) -> gym.Env:
    """Instantiates and configures a Gymnasium LunarLander environment.

    Args:
        env_id: Environment identifier (default: "LunarLander-v3").
        continuous: If True, uses continuous 2D action space; if False, uses 4 discrete actions.
        gravity: Acceleration due to gravity in m/s^2 (default: -10.0).
        enable_wind: Whether aerodynamic wind forces are applied.
        wind_power: Maximum linear wind force.
        turbulence_power: Maximum rotational turbulence force.
        render_mode: Render mode ("human", "rgb_array", or None for headless).
        seed: Random seed for deterministic reproducibility.
        reward_config: Optional reward shaping configuration.
        domain_randomization_config: Optional domain randomization configuration.
        curriculum_manager: Optional active CurriculumManager instance.
        **kwargs: Additional keyword arguments passed directly to gym.make.

    Returns:
        Configured gym.Env instance with requested wrappers.
    """
    env = gym.make(
        id=env_id,
        continuous=continuous,
        gravity=gravity,
        enable_wind=enable_wind,
        wind_power=wind_power,
        turbulence_power=turbulence_power,
        render_mode=render_mode,
        **kwargs,
    )

    # 1. Apply Domain Randomization wrapper if requested
    if domain_randomization_config is not None:
        dr_cfg = (
            load_domain_randomization_config(domain_randomization_config)
            if not isinstance(domain_randomization_config, DomainRandomizationConfig)
            else domain_randomization_config
        )
        env = DomainRandomizationWrapper(env, config=dr_cfg)

    # 2. Apply Curriculum wrapper if requested
    if curriculum_manager is not None:
        env = CurriculumEnvWrapper(env, curriculum_manager=curriculum_manager)

    # 3. Apply Reward Shaping wrapper if requested
    if reward_config is not None:
        r_cfg = load_reward_config(reward_config) if not isinstance(reward_config, RewardConfig) else reward_config
        env = RocketRewardShapingWrapper(env, config=r_cfg)

    if seed is not None:
        env.reset(seed=seed)
        env.action_space.seed(seed)
        env.observation_space.seed(seed)

    return env
