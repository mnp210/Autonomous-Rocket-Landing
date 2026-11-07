"""Gymnasium LunarLander environment setup and wrappers."""

from typing import Any, Dict, Optional
import gymnasium as gym


def make_lunar_lander_env(
    continuous: bool = True,
    gravity: float = -10.0,
    enable_wind: bool = False,
    wind_power: float = 15.0,
    turbulence_power: float = 1.5,
    render_mode: Optional[str] = None,
    **kwargs: Any,
) -> gym.Env:
    """Creates and configures a LunarLander environment.

    Args:
        continuous: If True, uses continuous action space (main engine and side engines).
        gravity: Acceleration due to gravity.
        enable_wind: Whether to simulate aerodynamic wind perturbations.
        wind_power: Wind force magnitude.
        turbulence_power: Wind turbulence strength.
        render_mode: Render mode ('human', 'rgb_array', or None).

    Returns:
        Configured Gymnasium environment.
    """
    env = gym.make(
        "LunarLander-v3" if "LunarLander-v3" in gym.envs.registry else "LunarLander-v2",
        continuous=continuous,
        gravity=gravity,
        enable_wind=enable_wind,
        wind_power=wind_power,
        turbulence_power=turbulence_power,
        render_mode=render_mode,
        **kwargs,
    )
    return env
