"""Curriculum learning manager and environment wrappers for progressive difficulty training."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import gymnasium as gym
import numpy as np
import yaml

from environments.domain_randomization import (
    DomainRandomizationConfig,
    DomainRandomizationWrapper,
    WindRandomizationConfig,
    InitialPerturbationConfig,
    load_domain_randomization_config,
)


@dataclass
class CurriculumStage:
    """Specification of an individual curriculum difficulty stage."""
    stage_id: int
    name: str
    description: str
    randomization_config: DomainRandomizationConfig


def get_default_curriculum_stages() -> Dict[int, CurriculumStage]:
    """Builds standard 5-stage progressive difficulty ladder."""
    return {
        0: CurriculumStage(
            stage_id=0,
            name="Stage 0: Standard Environment",
            description="Standard LunarLander with fixed nominal physics",
            randomization_config=DomainRandomizationConfig(enabled=False),
        ),
        1: CurriculumStage(
            stage_id=1,
            name="Stage 1: Moderate Gravity Variation",
            description="Slight gravity modulation without wind",
            randomization_config=DomainRandomizationConfig(
                enabled=True,
                mode="randomized",
                gravity_range=(-11.0, -9.0),
                wind=WindRandomizationConfig(probability=0.0),
            ),
        ),
        2: CurriculumStage(
            stage_id=2,
            name="Stage 2: Mild Wind Introduction",
            description="Moderate gravity with mild aerodynamic wind",
            randomization_config=DomainRandomizationConfig(
                enabled=True,
                mode="randomized",
                gravity_range=(-11.0, -9.0),
                wind=WindRandomizationConfig(probability=0.6, power_range=(5.0, 15.0), turbulence_range=(0.2, 1.0)),
            ),
        ),
        3: CurriculumStage(
            stage_id=3,
            name="Stage 3: High Wind and Turbulence",
            description="Broader gravity with strong wind and turbulence",
            randomization_config=DomainRandomizationConfig(
                enabled=True,
                mode="randomized",
                gravity_range=(-12.0, -8.0),
                wind=WindRandomizationConfig(probability=0.8, power_range=(10.0, 20.0), turbulence_range=(0.5, 2.0)),
            ),
        ),
        4: CurriculumStage(
            stage_id=4,
            name="Stage 4: Combined Extreme Stressors",
            description="Extreme gravity shifts, high-velocity wind, turbulence, and initial impulses",
            randomization_config=DomainRandomizationConfig(
                enabled=True,
                mode="randomized",
                gravity_range=(-13.0, -7.0),
                wind=WindRandomizationConfig(probability=0.9, power_range=(5.0, 25.0), turbulence_range=(0.5, 2.5)),
                initial_perturbation=InitialPerturbationConfig(enabled=True, horizontal_impulse_range=(-150.0, 150.0)),
            ),
        ),
    }


@dataclass
class CurriculumRules:
    """Rules and thresholds governing curriculum stage advancement and rollback."""
    min_eval_episodes: int = 20
    success_threshold: float = 0.70
    rollback_threshold: float = 0.30
    min_consecutive_passes: int = 2
    min_steps_per_stage: int = 20000


@dataclass
class CurriculumConfig:
    """Master curriculum configuration structure."""
    name: str = "Progressive_Environmental_Stressors"
    rules: CurriculumRules = field(default_factory=CurriculumRules)
    stages: Dict[int, CurriculumStage] = field(default_factory=dict)

    def __post_init__(self):
        if not self.stages:
            self.stages = get_default_curriculum_stages()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CurriculumConfig":
        curr_meta = data.get("curriculum", {})
        rules = CurriculumRules(
            min_eval_episodes=int(curr_meta.get("min_eval_episodes", 20)),
            success_threshold=float(curr_meta.get("success_threshold", 0.70)),
            rollback_threshold=float(curr_meta.get("rollback_threshold", 0.30)),
            min_consecutive_passes=int(curr_meta.get("min_consecutive_passes", 2)),
            min_steps_per_stage=int(curr_meta.get("min_steps_per_stage", 20000)),
        )

        stages: Dict[int, CurriculumStage] = {}
        stages_data = data.get("stages", {})
        for stage_key, stage_info in stages_data.items():
            sid = int(stage_key)
            rand_dict = stage_info.get("randomization", {})
            rand_cfg = DomainRandomizationConfig.from_dict(rand_dict)
            stages[sid] = CurriculumStage(
                stage_id=sid,
                name=stage_info.get("name", f"Stage {sid}"),
                description=stage_info.get("description", ""),
                randomization_config=rand_cfg,
            )

        return cls(
            name=curr_meta.get("name", "Progressive_Environmental_Stressors"),
            rules=rules,
            stages=stages,
        )


def load_curriculum_config(path_or_dict: Union[str, Path, Dict[str, Any]]) -> CurriculumConfig:
    """Loads curriculum configuration from YAML or dictionary."""
    if isinstance(path_or_dict, (str, Path)):
        p = Path(path_or_dict)
        if not p.is_file():
            raise FileNotFoundError(f"Curriculum config not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return CurriculumConfig.from_dict(raw)
    elif isinstance(path_or_dict, dict):
        return CurriculumConfig.from_dict(path_or_dict)
    elif isinstance(path_or_dict, CurriculumConfig):
        return path_or_dict
    else:
        raise TypeError(f"Invalid curriculum config type: {type(path_or_dict)}")


class CurriculumManager:
    """Manages progression, rollback, and state transitions across curriculum stages."""

    def __init__(self, config: Optional[Union[CurriculumConfig, Dict[str, Any], str]] = None):
        if config is None:
            self.config = CurriculumConfig()
        elif isinstance(config, CurriculumConfig):
            self.config = config
        else:
            self.config = load_curriculum_config(config)

        self.current_stage_id: int = 0
        self.consecutive_passes: int = 0
        self.steps_in_current_stage: int = 0
        self.history: List[Dict[str, Any]] = []

    @property
    def max_stage_id(self) -> int:
        return max(self.config.stages.keys()) if self.config.stages else 0

    @property
    def current_stage(self) -> CurriculumStage:
        if self.current_stage_id in self.config.stages:
            return self.config.stages[self.current_stage_id]
        # Fallback minimal stage
        return CurriculumStage(
            stage_id=0,
            name="Stage 0: Default",
            description="Fallback standard environment",
            randomization_config=DomainRandomizationConfig(enabled=False),
        )

    def record_step_progress(self, steps: int = 1) -> None:
        """Increments step count in the active stage."""
        self.steps_in_current_stage += steps

    def evaluate_progression(
        self,
        landing_success_rate: float,
        eval_episodes: int,
        current_timestep: int = 0,
    ) -> Tuple[bool, str]:
        """Evaluates whether to advance, rollback, or sustain current curriculum stage.

        Progression requires:
            - At least rules.min_eval_episodes evaluated
            - Success rate >= rules.success_threshold
            - At least rules.min_steps_per_stage spent in current stage
            - Reaching threshold for rules.min_consecutive_passes consecutive evaluations

        Rollback triggers when:
            - Current stage > 0
            - Success rate < rules.rollback_threshold

        Returns:
            Tuple of (stage_changed: bool, transition_reason: str)
        """
        rules = self.config.rules

        # Check sufficiency of evaluation sample
        if eval_episodes < rules.min_eval_episodes:
            return False, f"Insufficient eval episodes ({eval_episodes} < {rules.min_eval_episodes})"

        # Check for advancement
        if landing_success_rate >= rules.success_threshold:
            self.consecutive_passes += 1
            if self.consecutive_passes >= rules.min_consecutive_passes:
                if self.steps_in_current_stage >= rules.min_steps_per_stage:
                    if self.current_stage_id < self.max_stage_id:
                        old_id = self.current_stage_id
                        self.current_stage_id += 1
                        self.consecutive_passes = 0
                        self.steps_in_current_stage = 0
                        reason = (
                            f"ADVANCE: Stage {old_id} -> {self.current_stage_id} "
                            f"(Success: {landing_success_rate*100:.1f}% >= {rules.success_threshold*100:.1f}%)"
                        )
                        self._log_transition("advance", old_id, self.current_stage_id, landing_success_rate, current_timestep, reason)
                        return True, reason
                    else:
                        return False, "SUSTAIN: Policy has already mastered the final curriculum stage!"
                else:
                    return False, f"WAIT: Min steps in stage not met ({self.steps_in_current_stage:,} < {rules.min_steps_per_stage:,})"
            else:
                return False, f"PROGRESSING: Pass {self.consecutive_passes}/{rules.min_consecutive_passes} at {landing_success_rate*100:.1f}%"

        # Check for rollback
        elif landing_success_rate < rules.rollback_threshold and self.current_stage_id > 0:
            old_id = self.current_stage_id
            self.current_stage_id -= 1
            self.consecutive_passes = 0
            self.steps_in_current_stage = 0
            reason = (
                f"ROLLBACK: Stage {old_id} -> {self.current_stage_id} "
                f"(Success {landing_success_rate*100:.1f}% < {rules.rollback_threshold*100:.1f}%)"
            )
            self._log_transition("rollback", old_id, self.current_stage_id, landing_success_rate, current_timestep, reason)
            return True, reason

        else:
            self.consecutive_passes = 0
            return False, f"SUSTAIN: Success rate {landing_success_rate*100:.1f}% within current stage operational range"

    def _log_transition(
        self,
        event_type: str,
        from_stage: int,
        to_stage: int,
        success_rate: float,
        timestep: int,
        reason: str,
    ) -> None:
        self.history.append({
            "event": event_type,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "success_rate": round(success_rate, 4),
            "timestep": timestep,
            "reason": reason,
        })


class CurriculumEnvWrapper(gym.Wrapper):
    """Wrapper dynamically coupling Gymnasium environment to CurriculumManager stages."""

    def __init__(
        self,
        env: gym.Env,
        curriculum_manager: Optional[CurriculumManager] = None,
        config: Optional[Union[CurriculumConfig, Dict[str, Any], str]] = None,
    ):
        super().__init__(env)
        self.manager = curriculum_manager or CurriculumManager(config)

        # Wrap with domain randomization wrapper if not already present
        if not isinstance(self.env, DomainRandomizationWrapper):
            self.dr_wrapper = DomainRandomizationWrapper(
                self.env,
                config=self.manager.current_stage.randomization_config,
            )
            self.env = self.dr_wrapper
        else:
            self.dr_wrapper = self.env
            self.dr_wrapper.config = self.manager.current_stage.randomization_config

    def set_stage(self, stage_id: int) -> None:
        """Manually sets active curriculum stage."""
        if stage_id in self.manager.config.stages:
            self.manager.current_stage_id = stage_id
            self.dr_wrapper.config = self.manager.current_stage.randomization_config
        else:
            raise ValueError(f"Unknown curriculum stage ID: {stage_id}. Available: {list(self.manager.config.stages.keys())}")

    def update_to_current_stage(self) -> None:
        """Synchronizes domain randomization parameters with the active manager stage."""
        self.dr_wrapper.config = self.manager.current_stage.randomization_config

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        self.update_to_current_stage()
        obs, info = self.env.reset(seed=seed, options=options)
        info["curriculum_stage"] = self.manager.current_stage_id
        info["curriculum_stage_name"] = self.manager.current_stage.name
        return obs, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        obs, reward, term, trunc, info = self.env.step(action)
        info["curriculum_stage"] = self.manager.current_stage_id
        return obs, reward, term, trunc, info
