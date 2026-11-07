"""Configuration schemas and data structures for reward shaping strategies."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml


class RewardStrategy(str, Enum):
    """Supported reward shaping paradigms."""
    BASELINE = "baseline"
    POTENTIAL_BASED = "potential_based"
    ENERGY_AWARE = "energy_aware"


@dataclass
class PotentialWeights:
    """Coefficients for potential function terms."""
    distance: float = 1.0
    velocity: float = 0.5
    angle: float = 1.0
    angular_velocity: float = 0.5
    leg_contact: float = 1.0


@dataclass
class StateNormalizers:
    """Normalization scales for observation components."""
    x: float = 1.5
    y: float = 1.5
    vx: float = 2.0
    vy: float = 2.0
    theta: float = 0.7854  # pi/4 rad (~45 degrees)
    theta_dot: float = 2.0


@dataclass
class EnergyPenalties:
    """Penalties for engine activations and high-frequency actuation chattering."""
    main_engine: float = 0.05
    side_thruster: float = 0.01
    control_switch: float = 0.005


@dataclass
class RewardConfig:
    """Master configuration for reward shaping.

    Attributes:
        strategy: 'baseline', 'potential_based', or 'energy_aware'.
        gamma: Discount factor matching PPO gamma for PBRS policy invariance.
        shaping_scale: Multiplier for potential difference term F(s, s').
        zero_terminal_potential: If True, enforces Phi(s_term) = 0 as per Ng et al. (1999).
        potential_weights: Weightings for each potential component.
        normalizers: Scale dividers for normalizing states into standard ranges.
        energy_penalties: Engine and actuation cost parameters.
    """
    strategy: RewardStrategy = RewardStrategy.BASELINE
    gamma: float = 0.99
    shaping_scale: float = 1.0
    zero_terminal_potential: bool = True
    potential_weights: PotentialWeights = field(default_factory=PotentialWeights)
    normalizers: StateNormalizers = field(default_factory=StateNormalizers)
    energy_penalties: EnergyPenalties = field(default_factory=EnergyPenalties)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RewardConfig":
        """Instantiates RewardConfig from a dictionary (e.g. parsed from YAML)."""
        strat_val = data.get("strategy", RewardStrategy.BASELINE)
        strategy = RewardStrategy(strat_val) if isinstance(strat_val, str) else strat_val

        pw_data = data.get("potential_weights", {})
        norm_data = data.get("normalizers", {})
        ep_data = data.get("energy_penalties", {})

        return cls(
            strategy=strategy,
            gamma=float(data.get("gamma", 0.99)),
            shaping_scale=float(data.get("shaping_scale", 1.0)),
            zero_terminal_potential=bool(data.get("zero_terminal_potential", True)),
            potential_weights=PotentialWeights(**pw_data) if isinstance(pw_data, dict) else pw_data,
            normalizers=StateNormalizers(**norm_data) if isinstance(norm_data, dict) else norm_data,
            energy_penalties=EnergyPenalties(**ep_data) if isinstance(ep_data, dict) else ep_data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes configuration to dictionary."""
        d = asdict(self)
        d["strategy"] = self.strategy.value
        return d


def load_reward_config(path_or_dict: Union[str, Path, Dict[str, Any]]) -> RewardConfig:
    """Loads RewardConfig from file path or dictionary."""
    if isinstance(path_or_dict, (str, Path)):
        p = Path(path_or_dict)
        if not p.is_file():
            raise FileNotFoundError(f"Reward config file not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return RewardConfig.from_dict(raw)
    elif isinstance(path_or_dict, dict):
        return RewardConfig.from_dict(path_or_dict)
    elif isinstance(path_or_dict, RewardConfig):
        return path_or_dict
    else:
        raise TypeError(f"Invalid reward config source: {type(path_or_dict)}")
