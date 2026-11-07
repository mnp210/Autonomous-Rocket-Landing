"""Training pipeline for Autonomous Rocket Landing with modular reward shaping.

Handles environment initialization with Monitor, reproducible seeding,
TensorBoard logging, checkpointing, periodic evaluation callbacks, and
artifact management under unique run identifiers for baseline, potential-based,
and energy-aware reward configurations.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
import gymnasium as gym
import numpy as np
import torch
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor

from environments.env_loader import make_environment
from agents.ppo_agent import create_ppo_agent, load_config_file
from rewards.reward_config import RewardConfig, RewardStrategy, load_reward_config
from training.callbacks import create_training_callbacks


def set_reproducible_seed(seed: int) -> None:
    """Sets random seeds for reproducibility across NumPy and PyTorch."""
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def generate_run_id(strategy_name: str = "baseline") -> str:
    """Generates a timestamped unique experiment identifier."""
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ppo_{strategy_name}_{now_str}"


def train_baseline_agent(
    config_path: Union[str, Path] = "configs/ppo_config.yaml",
    reward_config_path: Optional[Union[str, Path]] = None,
    reward_strategy: Optional[str] = None,
    total_timesteps: Optional[int] = None,
    seed: Optional[int] = None,
    run_id: Optional[str] = None,
    verbose: int = 1,
) -> Dict[str, Any]:
    """Executes PPO agent training according to configuration and chosen reward strategy.

    Args:
        config_path: Path to PPO YAML configuration file.
        reward_config_path: Optional path to reward shaping YAML file (e.g. configs/reward_config.yaml).
        reward_strategy: Optional strategy override ('baseline', 'potential_based', 'energy_aware').
        total_timesteps: Overrides total timesteps from config if provided.
        seed: Overrides random seed from config if provided.
        run_id: Custom run identifier; if None, generates unique timestamped ID.
        verbose: Verbosity level for logger.

    Returns:
        Dictionary containing run summary metadata and paths to saved artifacts.
    """
    config = load_config_file(config_path)

    # Resolve reward configuration
    if reward_config_path is not None:
        reward_cfg = load_reward_config(reward_config_path)
    elif "reward" in config:
        reward_cfg = RewardConfig.from_dict(config["reward"])
    else:
        reward_cfg = RewardConfig(strategy=RewardStrategy.BASELINE)

    if reward_strategy is not None:
        reward_cfg.strategy = RewardStrategy(reward_strategy)

    strategy_name = reward_cfg.strategy.value

    # Resolve parameters
    env_cfg = config.get("environment", {})
    train_cfg = config.get("training", {})
    paths_cfg = config.get("paths", {})

    actual_seed = seed if seed is not None else env_cfg.get("seed", 42)
    actual_timesteps = total_timesteps if total_timesteps is not None else train_cfg.get("total_timesteps", 500000)
    actual_run_id = run_id or generate_run_id(strategy_name)

    set_reproducible_seed(actual_seed)

    # Establish directories with unique run_id isolation
    base_models_dir = Path(paths_cfg.get("models_dir", "models")) / strategy_name / actual_run_id
    base_logs_dir = Path(paths_cfg.get("logs_dir", "logs")) / strategy_name / actual_run_id
    base_exp_dir = Path(paths_cfg.get("experiments_dir", "experiments")) / strategy_name / actual_run_id

    checkpoints_dir = base_models_dir / "checkpoints"
    best_model_dir = base_models_dir / "best_model"
    eval_log_dir = base_logs_dir / "eval"

    base_models_dir.mkdir(parents=True, exist_ok=True)
    base_logs_dir.mkdir(parents=True, exist_ok=True)
    base_exp_dir.mkdir(parents=True, exist_ok=True)

    # Initialize environments with Monitor wrapper
    env_id = env_cfg.get("env_id", "LunarLander-v3")
    raw_train_env = make_environment(
        env_id=env_id,
        continuous=False,
        seed=actual_seed,
        reward_config=reward_cfg if strategy_name != "baseline" else None,
    )
    train_env = Monitor(raw_train_env, filename=str(base_logs_dir / "train_monitor.csv"))

    # Evaluation environment evaluates on original environment metrics
    raw_eval_env = make_environment(
        env_id=env_id,
        continuous=False,
        seed=actual_seed + 1000,
        reward_config=reward_cfg if strategy_name != "baseline" else None,
    )
    eval_env = Monitor(raw_eval_env, filename=str(base_logs_dir / "eval_monitor.csv"))

    if verbose > 0:
        print("=" * 80)
        print(f" STARTING PPO TRAINING | Strategy: {strategy_name.upper()} | Run ID: {actual_run_id}")
        print("=" * 80)
        print(f" Environment       : {env_id}")
        print(f" Reward Strategy   : {strategy_name}")
        print(f" Total Timesteps   : {actual_timesteps:,}")
        print(f" Random Seed       : {actual_seed}")
        print(f" Artifacts Root    : {base_models_dir}")
        print(f" TensorBoard Logs  : {base_logs_dir}")

    # Build PPO agent
    agent = create_ppo_agent(
        env=train_env,
        config=config,
        tensorboard_log=str(base_logs_dir),
        seed=actual_seed,
        verbose=verbose,
    )

    # Configure training callbacks
    checkpoint_freq = train_cfg.get("checkpoint_freq", 25000)
    eval_freq = train_cfg.get("eval_freq", 10000)
    eval_episodes = train_cfg.get("eval_episodes", 20)

    callbacks = create_training_callbacks(
        eval_env=eval_env,
        checkpoint_dir=str(checkpoints_dir),
        best_model_dir=str(best_model_dir),
        eval_log_dir=str(eval_log_dir),
        checkpoint_freq=checkpoint_freq,
        eval_freq=eval_freq,
        n_eval_episodes=eval_episodes,
        deterministic=True,
        verbose=verbose,
    )

    # Save active configuration snapshot in experiment directory
    snapshot_config_path = base_exp_dir / "config_snapshot.yaml"
    snapshot_data = {
        "ppo_config": config,
        "reward_config": reward_cfg.to_dict(),
    }
    with open(snapshot_config_path, "w", encoding="utf-8") as f:
        yaml.dump(snapshot_data, f, default_flow_style=False)

    start_time = datetime.now()

    # Launch training loop
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

    duration_seconds = (datetime.now() - start_time).total_seconds()

    # Save final policy
    final_model_path = base_models_dir / "final_model.zip"
    agent.save(str(final_model_path))

    summary: Dict[str, Any] = {
        "run_id": actual_run_id,
        "strategy": strategy_name,
        "environment": env_id,
        "total_timesteps": actual_timesteps,
        "seed": actual_seed,
        "start_time": start_time.isoformat(),
        "duration_seconds": round(duration_seconds, 2),
        "final_model_path": str(final_model_path),
        "best_model_dir": str(best_model_dir),
        "checkpoints_dir": str(checkpoints_dir),
        "tensorboard_log_dir": str(base_logs_dir),
        "config_snapshot": str(snapshot_config_path),
    }

    summary_file = base_exp_dir / "run_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if verbose > 0:
        print("\n" + "=" * 80)
        print(f" TRAINING COMPLETE | Strategy: {strategy_name.upper()}")
        print(f" Final Model Saved : {final_model_path}")
        print(f" Experiment Summary: {summary_file}")
        print("=" * 80)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PPO Agent on LunarLander-v3 with Reward Shaping")
    parser.add_argument("--config", type=str, default="configs/ppo_config.yaml", help="Path to PPO config file")
    parser.add_argument("--reward-config", type=str, default="configs/reward_config.yaml", help="Path to reward config file")
    parser.add_argument("--strategy", type=str, default=None, choices=["baseline", "potential_based", "energy_aware"], help="Reward strategy override")
    parser.add_argument("--timesteps", type=int, default=None, help="Override total training timesteps")
    parser.add_argument("--seed", type=int, default=None, help="Override random seed")
    parser.add_argument("--run-id", type=str, default=None, help="Custom experiment run identifier")
    parser.add_argument("--quiet", action="store_true", help="Minimize console logging")

    args = parser.parse_args()

    train_baseline_agent(
        config_path=args.config,
        reward_config_path=args.reward_config,
        reward_strategy=args.strategy,
        total_timesteps=args.timesteps,
        seed=args.seed,
        run_id=args.run_id,
        verbose=0 if args.quiet else 1,
    )
