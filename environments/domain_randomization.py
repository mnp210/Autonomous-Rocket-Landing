"""Domain Randomization Wrapper for Gymnasium LunarLander-v3.

Enables controlled, reproducible randomization of gravity, wind velocity,
turbulence intensity, and initial disturbance impulses at episode reset
without modifying library source code or introducing fragile monkeypatches.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import gymnasium as gym
import numpy as np
import yaml


@dataclass
class WindRandomizationConfig:
    """Configuration for aerodynamic wind disturbances."""
    probability: float = 0.5
    power_range: Tuple[float, float] = (5.0, 20.0)
    turbulence_range: Tuple[float, float] = (0.5, 2.0)


@dataclass
class InitialPerturbationConfig:
    """Configuration for initial disturbance perturbations at episode launch."""
    enabled: bool = False
    horizontal_impulse_range: Tuple[float, float] = (-200.0, 200.0)


@dataclass
class DomainRandomizationConfig:
    """Master configuration for domain randomization.

    Attributes:
        enabled: Whether domain randomization is active.
        mode: 'randomized' (samples within ranges) or 'fixed' (uses nominal/target values).
        gravity_range: Range [min, max] for vertical gravity acceleration (m/s^2).
        fixed_gravity: Gravity value when mode is 'fixed'.
        fixed_enable_wind: Wind active flag when mode is 'fixed'.
        fixed_wind_power: Wind magnitude when mode is 'fixed'.
        fixed_turbulence_power: Turbulence magnitude when mode is 'fixed'.
        wind: Aerodynamic wind randomization parameters.
        initial_perturbation: Initial kinetic perturbations applied to lander.
    """
    enabled: bool = True
    mode: str = "randomized"
    gravity_range: Tuple[float, float] = (-13.0, -7.0)
    fixed_gravity: float = -10.0
    fixed_enable_wind: bool = False
    fixed_wind_power: float = 15.0
    fixed_turbulence_power: float = 1.5
    wind: WindRandomizationConfig = field(default_factory=WindRandomizationConfig)
    initial_perturbation: InitialPerturbationConfig = field(default_factory=InitialPerturbationConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainRandomizationConfig":
        """Builds configuration from a parsed dictionary."""
        wind_data = data.get("wind", {})
        init_data = data.get("initial_perturbation", {})

        gravity_raw = data.get("gravity_range", (-13.0, -7.0))
        gravity_range = tuple(gravity_raw) if isinstance(gravity_raw, list) else gravity_raw

        wind_power_raw = wind_data.get("power_range", (5.0, 20.0))
        wind_turb_raw = wind_data.get("turbulence_range", (0.5, 2.0))
        init_imp_raw = init_data.get("horizontal_impulse_range", (-200.0, 200.0))

        wind_cfg = WindRandomizationConfig(
            probability=float(wind_data.get("probability", 0.5)),
            power_range=tuple(wind_power_raw) if isinstance(wind_power_raw, list) else wind_power_raw,
            turbulence_range=tuple(wind_turb_raw) if isinstance(wind_turb_raw, list) else wind_turb_raw,
        )

        init_cfg = InitialPerturbationConfig(
            enabled=bool(init_data.get("enabled", False)),
            horizontal_impulse_range=tuple(init_imp_raw) if isinstance(init_imp_raw, list) else init_imp_raw,
        )

        return cls(
            enabled=bool(data.get("enabled", True)),
            mode=str(data.get("mode", "randomized")),
            gravity_range=gravity_range,
            fixed_gravity=float(data.get("fixed_gravity", -10.0)),
            fixed_enable_wind=bool(data.get("fixed_enable_wind", False)),
            fixed_wind_power=float(data.get("fixed_wind_power", 15.0)),
            fixed_turbulence_power=float(data.get("fixed_turbulence_power", 1.5)),
            wind=wind_cfg,
            initial_perturbation=init_cfg,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts configuration to primitive dictionary."""
        d = asdict(self)
        d["gravity_range"] = list(self.gravity_range)
        d["wind"]["power_range"] = list(self.wind.power_range)
        d["wind"]["turbulence_range"] = list(self.wind.turbulence_range)
        d["initial_perturbation"]["horizontal_impulse_range"] = list(self.initial_perturbation.horizontal_impulse_range)
        return d


def load_domain_randomization_config(path_or_dict: Union[str, Path, Dict[str, Any]]) -> DomainRandomizationConfig:
    """Loads configuration from YAML file path or dictionary."""
    if isinstance(path_or_dict, (str, Path)):
        p = Path(path_or_dict)
        if not p.is_file():
            raise FileNotFoundError(f"Domain randomization config not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return DomainRandomizationConfig.from_dict(raw)
    elif isinstance(path_or_dict, dict):
        return DomainRandomizationConfig.from_dict(path_or_dict)
    elif isinstance(path_or_dict, DomainRandomizationConfig):
        return path_or_dict
    else:
        raise TypeError(f"Invalid domain randomization source type: {type(path_or_dict)}")


class DomainRandomizationWrapper(gym.Wrapper):
    """Gymnasium environment wrapper for domain randomization in LunarLander-v3.

    Dynamically modulates Box2D physics parameters prior to environment world creation on each reset.
    Fully maintains observation and action spaces and logs environmental parameters in info.
    """

    def __init__(
        self,
        env: gym.Env,
        config: Optional[Union[DomainRandomizationConfig, Dict[str, Any], str]] = None,
    ):
        super().__init__(env)
        if config is None:
            self.config = DomainRandomizationConfig(enabled=False)
        elif isinstance(config, DomainRandomizationConfig):
            self.config = config
        else:
            self.config = load_domain_randomization_config(config)

        self.np_random = np.random.default_rng()
        self.current_params: Dict[str, Any] = {
            "gravity": -10.0,
            "enable_wind": False,
            "wind_power": 15.0,
            "turbulence_power": 1.5,
            "initial_impulse_x": 0.0,
        }

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Samples new physical parameters and rebuilds the Box2D simulation world."""
        if seed is not None:
            self.np_random = np.random.default_rng(seed)

        if self.config.enabled:
            if self.config.mode == "randomized":
                # Sample vertical gravity
                g_min, g_max = self.config.gravity_range
                sampled_gravity = float(self.np_random.uniform(g_min, g_max))

                # Sample wind activation and forces
                wind_active = bool(self.np_random.random() < self.config.wind.probability)
                if wind_active:
                    w_min, w_max = self.config.wind.power_range
                    t_min, t_max = self.config.wind.turbulence_range
                    sampled_wind_power = float(self.np_random.uniform(w_min, w_max))
                    sampled_turbulence_power = float(self.np_random.uniform(t_min, t_max))
                else:
                    sampled_wind_power = 0.0
                    sampled_turbulence_power = 0.0

                # Sample initial impulse
                if self.config.initial_perturbation.enabled:
                    imp_min, imp_max = self.config.initial_perturbation.horizontal_impulse_range
                    sampled_impulse_x = float(self.np_random.uniform(imp_min, imp_max))
                else:
                    sampled_impulse_x = 0.0

            else:  # Fixed mode
                sampled_gravity = self.config.fixed_gravity
                wind_active = self.config.fixed_enable_wind
                sampled_wind_power = self.config.fixed_wind_power
                sampled_turbulence_power = self.config.fixed_turbulence_power
                sampled_impulse_x = 0.0

            # Apply directly to the underlying LunarLander before world construction in reset()
            unwrapped = self.env.unwrapped
            unwrapped.gravity = sampled_gravity
            unwrapped.enable_wind = wind_active
            unwrapped.wind_power = sampled_wind_power
            unwrapped.turbulence_power = sampled_turbulence_power

            self.current_params = {
                "gravity": round(sampled_gravity, 3),
                "enable_wind": wind_active,
                "wind_power": round(sampled_wind_power, 3),
                "turbulence_power": round(sampled_turbulence_power, 3),
                "initial_impulse_x": round(sampled_impulse_x, 3),
            }

        else:
            # Baseline parameters
            self.current_params = {
                "gravity": -10.0,
                "enable_wind": False,
                "wind_power": 15.0,
                "turbulence_power": 1.5,
                "initial_impulse_x": 0.0,
            }

        obs, info = self.env.reset(seed=seed, options=options)

        # Apply initial horizontal perturbation impulse if configured
        if self.config.enabled and self.config.initial_perturbation.enabled and self.current_params["initial_impulse_x"] != 0.0:
            unwrapped = self.env.unwrapped
            if hasattr(unwrapped, "lander") and unwrapped.lander is not None:
                impulse = (self.current_params["initial_impulse_x"], 0.0)
                unwrapped.lander.ApplyLinearImpulse(impulse, unwrapped.lander.worldCenter, True)
                # Refresh observation to reflect initial impulse velocity without calling non-existent _get_obs()
                # LunarLander velocity scaling factor is (VIEWPORT_W / SCALE / 2) / FPS = 0.2
                if hasattr(unwrapped.lander, "mass") and unwrapped.lander.mass > 0:
                    delta_obs_vx = (self.current_params["initial_impulse_x"] / unwrapped.lander.mass) * 0.2
                    obs = np.array(obs, copy=True, dtype=np.float32)
                    obs[2] += delta_obs_vx

        info["env_params"] = dict(self.current_params)
        return obs, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        info["env_params"] = dict(self.current_params)
        return obs, reward, terminated, truncated, info
