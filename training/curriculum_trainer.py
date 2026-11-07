"""Curriculum Trainer for Autonomous Rocket Landing.

Supports 4 rigorous experimental paradigms:
  A: Standard PPO without randomization (Control)
  B: PPO with Domain Randomization only
  C: PPO with Curriculum Learning only
  D: PPO with Curriculum Learning + Domain Randomization

Tracks rolling evaluation landing success rates, executes rule-based stage progression
and rollbacks, checkpoints stage milestones, and logs to TensorBoard.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import gymnasium as gym
import numpy as np
import torch
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor

from environments.env_loader import make_environment
from environments.curriculum import (
    CurriculumConfig,
    CurriculumManager,
    CurriculumEnvWrapper,
    load_curriculum_config,
)
from environments.domain_randomization import (
    DomainRandomizationConfig,
    DomainRandomizationWrapper,
    load_domain_randomization_config,
)
from agents.ppo_agent import create_ppo_agent, load_config_file
from rewards.reward_config import RewardConfig, RewardStrategy, load_reward_config
from evaluation.evaluate import evaluate_policy


class CurriculumProgressionCallback(BaseCallback):
    """Callback managing curriculum evaluation, stage progression, rollbacks, and milestone checkpoints."""

    def __init__(
        self,
        eval_env: gym.Env,
        curriculum_manager: CurriculumManager,
        train_env_wrapper: Optional[CurriculumEnvWrapper],
        eval_freq: int = 10000,
        n_eval_episodes: int = 20,
        stage_checkpoint_dir: Optional[Path] = None,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.eval_env = eval_env
        self.manager = curriculum_manager
        self.train_env_wrapper = train_env_wrapper
        self.eval_freq = eval_freq
        self.n_eval_episodes = n_eval_episodes
        self.stage_checkpoint_dir = stage_checkpoint_dir

    def _on_step(self) -> bool:
        self.manager.record_step_progress(1)

        if self.n_calls % self.eval_freq == 0:
            current_stage_id = self.manager.current_stage_id

            # Evaluate policy on the current curriculum stage
            if isinstance(self.eval_env.unwrapped, gym.Env) and self.train_env_wrapper:
                # Sync eval environment to current stage
                if hasattr(self.eval_env, "set_stage"):
                    self.eval_env.set_stage(current_stage_id)
                elif hasattr(self.eval_env, "env") and hasattr(self.eval_env.env, "set_stage"):
                    self.eval_env.env.set_stage(current_stage_id)

            metrics, _ = evaluate_policy(
                model=self.model,
                env=self.eval_env,
                n_episodes=self.n_eval_episodes,
                deterministic=True,
            )

            success_rate = metrics["landing_success_rate"]
            mean_reward = metrics["mean_episode_reward"]

            # Log to TensorBoard
            self.logger.record("curriculum/stage_id", current_stage_id)
            self.logger.record("curriculum/eval_success_rate", success_rate)
            self.logger.record("curriculum/eval_mean_reward", mean_reward)

            # Check progression
            changed, reason = self.manager.evaluate_progression(
                landing_success_rate=success_rate,
                eval_episodes=self.n_eval_episodes,
                current_timestep=self.num_timesteps,
            )

            if self.verbose > 0:
                print(f"\n[CURRICULUM EVAL @ {self.num_timesteps:,} steps] Stage {current_stage_id} ({self.manager.current_stage.name})")
                print(f"  • Landing Success Rate : {success_rate*100:.1f}%")
                print(f"  • Mean Episode Reward  : {mean_reward:.2f}")
                print(f"  • Curriculum Status    : {reason}")

            if changed and self.train_env_wrapper:
                new_stage_id = self.manager.current_stage_id
                self.train_env_wrapper.set_stage(new_stage_id)

                if self.stage_checkpoint_dir:
                    save_path = self.stage_checkpoint_dir / f"stage_{new_stage_id}_reached_{self.num_timesteps}_steps.zip"
                    self.model.save(str(save_path))
                    if self.verbose > 0:
                        print(f"  • Milestone Checkpoint : {save_path.name}")

        return True


def run_curriculum_experiment(
    experiment_type: str = "curriculum_and_dr",  # "standard", "dr_only", "curriculum_only", "curriculum_and_dr"
    ppo_config_path: Union[str, Path] = "configs/ppo_config.yaml",
    curriculum_config_path: Union[str, Path] = "configs/curriculum.yaml",
    dr_config_path: Union[str, Path] = "configs/domain_randomization.yaml",
    reward_strategy: str = "baseline",
    total_timesteps: Optional[int] = None,
    seed: int = 42,
    run_id: Optional[str] = None,
    verbose: int = 1,
    custom_model_dir: Optional[Union[str, Path]] = None,
    custom_log_dir: Optional[Union[str, Path]] = None,
    custom_exp_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Orchestrates training for one of the four Stage 4 experimental configurations.

    Args:
        experiment_type: 'standard', 'dr_only', 'curriculum_only', or 'curriculum_and_dr'.
        ppo_config_path: Path to PPO configuration YAML.
        curriculum_config_path: Path to Curriculum configuration YAML.
        dr_config_path: Path to Domain Randomization configuration YAML.
        reward_strategy: Fixed reward formulation to isolate environmental effects.
        total_timesteps: Override for total training steps.
        seed: Master random seed.
        run_id: Unique run identifier.
        verbose: Verbosity level.
        custom_model_dir: Optional explicit directory for model checkpoints.
        custom_log_dir: Optional explicit directory for logs.
        custom_exp_dir: Optional explicit directory for experiment metadata.

    Returns:
        Summary dictionary containing experiment metadata and paths.
    """
    valid_types = ["standard", "dr_only", "curriculum_only", "curriculum_and_dr"]
    if experiment_type not in valid_types:
        raise ValueError(f"Unknown experiment type: {experiment_type}. Choose from {valid_types}")

    ppo_cfg = load_config_file(ppo_config_path)
    reward_cfg = RewardConfig(strategy=RewardStrategy(reward_strategy))

    # Resolve timesteps
    train_cfg = ppo_cfg.get("training", {})
    actual_timesteps = total_timesteps if total_timesteps is not None else train_cfg.get("total_timesteps", 500000)

    # Generate unique ID
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    actual_run_id = run_id or f"exp_{experiment_type}_{reward_strategy}_{now_str}"

    # Setup directories
    base_model_dir = Path(custom_model_dir) if custom_model_dir else Path("models/curriculum") / experiment_type / actual_run_id
    base_log_dir = Path(custom_log_dir) if custom_log_dir else Path("logs/curriculum") / experiment_type / actual_run_id
    base_exp_dir = Path(custom_exp_dir) if custom_exp_dir else Path("experiments/curriculum") / experiment_type / actual_run_id

    stage_checkpoints_dir = base_model_dir / "stage_checkpoints"
    general_checkpoints_dir = base_model_dir / "checkpoints"

    base_model_dir.mkdir(parents=True, exist_ok=True)
    base_log_dir.mkdir(parents=True, exist_ok=True)
    base_exp_dir.mkdir(parents=True, exist_ok=True)
    stage_checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # Seed environments & PyTorch
    np.random.seed(seed)
    torch.manual_seed(seed)

    # Configure Environment based on experiment type
    curriculum_mgr = None
    train_curriculum_wrapper = None

    if experiment_type == "standard":
        # Pure nominal environment, no DR, no curriculum
        dr_cfg = DomainRandomizationConfig(enabled=False)
        raw_train_env = make_environment(
            env_id="LunarLander-v3",
            seed=seed,
            reward_config=reward_cfg if reward_strategy != "baseline" else None,
            domain_randomization_config=dr_cfg,
        )
        raw_eval_env = make_environment(
            env_id="LunarLander-v3",
            seed=seed + 1000,
            reward_config=reward_cfg if reward_strategy != "baseline" else None,
            domain_randomization_config=dr_cfg,
        )

    elif experiment_type == "dr_only":
        # Full static Domain Randomization throughout training
        dr_cfg = load_domain_randomization_config(dr_config_path)
        dr_cfg.enabled = True
        dr_cfg.mode = "randomized"
        raw_train_env = make_environment(
            env_id="LunarLander-v3",
            seed=seed,
            reward_config=reward_cfg if reward_strategy != "baseline" else None,
            domain_randomization_config=dr_cfg,
        )
        raw_eval_env = make_environment(
            env_id="LunarLander-v3",
            seed=seed + 1000,
            reward_config=reward_cfg if reward_strategy != "baseline" else None,
            domain_randomization_config=dr_cfg,
        )

    elif experiment_type in ("curriculum_only", "curriculum_and_dr"):
        curr_cfg = load_curriculum_config(curriculum_config_path)

        if experiment_type == "curriculum_only":
            # For curriculum only, stages 1-4 use fixed variations rather than stochastic distributions
            # Each stage has progressive deterministic environmental difficulty
            fixed_stage_params = {
                0: {"fixed_gravity": -10.0, "fixed_enable_wind": False, "fixed_wind_power": 0.0, "fixed_turbulence_power": 0.0},
                1: {"fixed_gravity": -10.5, "fixed_enable_wind": False, "fixed_wind_power": 0.0, "fixed_turbulence_power": 0.0},
                2: {"fixed_gravity": -10.0, "fixed_enable_wind": True, "fixed_wind_power": 10.0, "fixed_turbulence_power": 0.6},
                3: {"fixed_gravity": -11.0, "fixed_enable_wind": True, "fixed_wind_power": 15.0, "fixed_turbulence_power": 1.25},
                4: {"fixed_gravity": -12.0, "fixed_enable_wind": True, "fixed_wind_power": 20.0, "fixed_turbulence_power": 2.0},
            }
            for sid, stage in curr_cfg.stages.items():
                if sid in fixed_stage_params:
                    params = fixed_stage_params[sid]
                    stage.randomization_config.mode = "fixed"
                    stage.randomization_config.fixed_gravity = params["fixed_gravity"]
                    stage.randomization_config.fixed_enable_wind = params["fixed_enable_wind"]
                    stage.randomization_config.fixed_wind_power = params["fixed_wind_power"]
                    stage.randomization_config.fixed_turbulence_power = params["fixed_turbulence_power"]

        curriculum_mgr = CurriculumManager(curr_cfg)

        raw_train_env = make_environment(
            env_id="LunarLander-v3",
            seed=seed,
            reward_config=reward_cfg if reward_strategy != "baseline" else None,
            curriculum_manager=curriculum_mgr,
        )
        # Unwrap to identify CurriculumEnvWrapper
        train_curriculum_wrapper = raw_train_env

        raw_eval_env = make_environment(
            env_id="LunarLander-v3",
            seed=seed + 1000,
            reward_config=reward_cfg if reward_strategy != "baseline" else None,
            curriculum_manager=CurriculumManager(curr_cfg),
        )

    train_env = Monitor(raw_train_env, filename=str(base_log_dir / "train_monitor.csv"))
    eval_env = Monitor(raw_eval_env, filename=str(base_log_dir / "eval_monitor.csv"))

    if verbose > 0:
        print("=" * 80)
        print(f" LAUNCHING CURRICULUM/DR EXPERIMENT: {experiment_type.upper()}")
        print(f" Run Identifier   : {actual_run_id}")
        print(f" Reward Strategy  : {reward_strategy}")
        print(f" Total Timesteps  : {actual_timesteps:,}")
        print(f" Model Output     : {base_model_dir}")
        print(f" TensorBoard Logs : {base_log_dir}")
        print("=" * 80)

    # Initialize PPO agent
    agent = create_ppo_agent(
        env=train_env,
        config=ppo_cfg,
        tensorboard_log=str(base_log_dir),
        seed=seed,
        verbose=verbose,
    )

    # Configure callbacks
    callbacks_list = []
    checkpoint_freq = train_cfg.get("checkpoint_freq", 25000)
    eval_freq = train_cfg.get("eval_freq", 10000)
    eval_episodes = train_cfg.get("eval_episodes", 20)

    # Standard periodic checkpoint
    callbacks_list.append(
        CheckpointCallback(
            save_freq=checkpoint_freq,
            save_path=str(general_checkpoints_dir),
            name_prefix="ppo_checkpoint",
            save_vecnormalize=True,
            verbose=verbose,
        )
    )

    # Curriculum manager callback if active
    if curriculum_mgr is not None:
        callbacks_list.append(
            CurriculumProgressionCallback(
                eval_env=eval_env,
                curriculum_manager=curriculum_mgr,
                train_env_wrapper=train_curriculum_wrapper,
                eval_freq=eval_freq,
                n_eval_episodes=eval_episodes,
                stage_checkpoint_dir=stage_checkpoints_dir,
                verbose=verbose,
            )
        )

    callbacks = CallbackList(callbacks_list)

    # Record snapshot config
    snapshot = {
        "experiment_type": experiment_type,
        "reward_strategy": reward_strategy,
        "seed": seed,
        "total_timesteps": actual_timesteps,
        "ppo_config": ppo_cfg,
    }
    with open(base_exp_dir / "config_snapshot.yaml", "w", encoding="utf-8") as f:
        yaml.dump(snapshot, f, default_flow_style=False)

    start_time = datetime.now()
    try:
        agent.learn(
            total_timesteps=actual_timesteps,
            callback=callbacks,
            log_interval=train_cfg.get("log_interval", 10),
            reset_num_timesteps=True,
        )
    finally:
        train_env.close()
        eval_env.close()

    duration = (datetime.now() - start_time).total_seconds()
    final_model_path = base_model_dir / "final_model.zip"
    agent.save(str(final_model_path))

    summary: Dict[str, Any] = {
        "run_id": actual_run_id,
        "experiment_type": experiment_type,
        "reward_strategy": reward_strategy,
        "total_timesteps": actual_timesteps,
        "completed_timesteps": actual_timesteps,
        "seed": seed,
        "duration_seconds": round(duration, 2),
        "final_model_path": str(final_model_path),
        "curriculum_history": curriculum_mgr.history if curriculum_mgr else [],
        "tensorboard_log": str(base_log_dir),
    }

    summary_file = base_exp_dir / "run_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Also replicate in model directory for self-contained inspection
    if base_model_dir != base_exp_dir:
        with open(base_model_dir / "run_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    if verbose > 0:
        print("\n" + "=" * 80)
        print(f" EXPERIMENT FINISHED: {experiment_type.upper()}")
        print(f" Final Model Saved : {final_model_path}")
        print(f" Summary File      : {summary_file}")
        print("=" * 80)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curriculum & Domain Randomization Trainer for LunarLander-v3")
    parser.add_argument(
        "--type",
        type=str,
        default="curriculum_and_dr",
        choices=["standard", "dr_only", "curriculum_only", "curriculum_and_dr"],
        help="Experiment paradigm to execute",
    )
    parser.add_argument("--timesteps", type=int, default=None, help="Override training timesteps")
    parser.add_argument("--strategy", type=str, default="baseline", help="Reward strategy (baseline, potential_based, energy_aware)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--run-id", type=str, default=None, help="Custom experiment run ID")

    args = parser.parse_args()

    run_curriculum_experiment(
        experiment_type=args.type,
        reward_strategy=args.strategy,
        total_timesteps=args.timesteps,
        seed=args.seed,
        run_id=args.run_id,
        verbose=1,
    )
