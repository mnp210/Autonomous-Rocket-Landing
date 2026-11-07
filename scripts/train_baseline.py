"""CLI script to launch PPO agent training on LunarLander-v3.

Supports:
- Baseline (Gymnasium original reward)
- Potential-based reward shaping (PBRS)
- Energy-aware reward shaping (PBRS + thruster consumption penalty)

Usage:
    # Baseline control experiment:
    python scripts/train_baseline.py --strategy baseline --timesteps 500000

    # Potential-based reward shaping:
    python scripts/train_baseline.py --strategy potential_based --timesteps 500000

    # Energy-aware reward shaping:
    python scripts/train_baseline.py --strategy energy_aware --timesteps 500000
"""

import argparse
import sys
from pathlib import Path

# Add repository root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from training.train import train_baseline_agent


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Rocket Landing — Train PPO Agent with Reward Shaping Options"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="baseline",
        choices=["baseline", "potential_based", "energy_aware"],
        help="Reward shaping configuration to train with (default: baseline)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/ppo_config.yaml",
        help="Path to YAML PPO configuration file (default: configs/ppo_config.yaml)",
    )
    parser.add_argument(
        "--reward-config",
        type=str,
        default="configs/reward_config.yaml",
        help="Path to YAML reward shaping configuration file (default: configs/reward_config.yaml)",
    )
    parser.add_argument(
        "--timesteps",
        type=int,
        default=None,
        help="Override total training timesteps (e.g. 500000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override random seed for training and environments (e.g. 42)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Custom experiment run identifier (defaults to timestamped name)",
    )

    args = parser.parse_args()

    try:
        summary = train_baseline_agent(
            config_path=args.config,
            reward_config_path=args.reward_config,
            reward_strategy=args.strategy,
            total_timesteps=args.timesteps,
            seed=args.seed,
            run_id=args.run_id,
            verbose=1,
        )
        print("\nTraining run finished successfully.")
        print(f"Artifacts saved in: {summary['final_model_path']}")
    except KeyboardInterrupt:
        print("\n[WARNING] Training interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Training failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
