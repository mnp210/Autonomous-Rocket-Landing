"""CLI script to evaluate a trained PPO policy on LunarLander-v3.

Usage:
    # Run deterministic evaluation:
    python scripts/evaluate_baseline.py --model-path models/baseline/run_id/final_model.zip --episodes 50

    # Evaluate with trajectory telemetry plot:
    python scripts/evaluate_baseline.py --model-path models/baseline/run_id/final_model.zip --episodes 10 --plot-trajectory

    # Watch the trained agent fly in a rendered window:
    python scripts/evaluate_baseline.py --model-path models/baseline/run_id/final_model.zip --render --episodes 5
"""

import argparse
from pathlib import Path
import sys

# Add repository root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from evaluation.evaluate import run_evaluation
from visualization.reward_analysis import plot_episode_telemetry


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Rocket Landing — Evaluate Trained PPO Agent"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        required=True,
        help="Path to trained PPO model archive (.zip)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=50,
        help="Number of evaluation episodes to test (default: 50)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        choices=["baseline", "potential_based", "energy_aware"],
        help="Optional reward shaping strategy to instrument during evaluation",
    )
    parser.add_argument(
        "--reward-config",
        type=str,
        default=None,
        help="Path to custom reward config file (e.g. configs/reward_config.yaml)",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        default=True,
        help="Use deterministic policy actions (default: True)",
    )
    parser.add_argument(
        "--stochastic",
        dest="deterministic",
        action="store_false",
        help="Use stochastic policy actions instead of deterministic",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Render live simulation window",
    )
    parser.add_argument(
        "--renderer",
        type=str,
        default="cinematic",
        choices=["cinematic", "aerospace", "gymnasium"],
        help="Visual rendering backend when --render is active: 'cinematic' (cinematic tracking camera & dust), 'aerospace' (16:9 fixed), or 'gymnasium' (legacy 4:3)",
    )
    parser.add_argument(
        "--plot-trajectory",
        action="store_true",
        help="Generate and save multi-panel telemetry and reward decomposition plot",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default=None,
        help="Directory to save evaluation_metrics.json and episode records CSV",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for evaluation (default: 42)",
    )

    args = parser.parse_args()

    model_path = Path(args.model_path)
    if not model_path.exists() and not model_path.with_suffix(".zip").exists():
        print(f"[ERROR] Specified model file does not exist: {model_path}")
        sys.exit(1)

    save_dir = Path(args.save_dir) if args.save_dir else model_path.parent / "eval_results"
    save_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(" EVALUATING PPO ROCKET LANDING AGENT")
    print("=" * 80)
    print(f" Model Path     : {model_path}")
    print(f" Test Episodes  : {args.episodes}")
    print(f" Deterministic  : {args.deterministic}")
    print(f" Render Mode    : {args.renderer.upper() if args.render else 'None (headless)'}")
    print(f" Output Dir     : {save_dir}")

    render_mode = "human" if args.render else None

    # Resolve reward configuration if requested
    reward_cfg = None
    if args.reward_config:
        reward_cfg = args.reward_config
    elif args.strategy:
        reward_cfg = {"strategy": args.strategy}

    metrics = run_evaluation(
        model_path=model_path,
        n_episodes=args.episodes,
        deterministic=args.deterministic,
        render_mode=render_mode,
        renderer_type=args.renderer,
        output_dir=save_dir,
        reward_config=reward_cfg,
        seed=args.seed,
        record_trajectory=args.plot_trajectory,
    )

    # If telemetry plot requested, plot the recorded sample trajectory
    if args.plot_trajectory and "sample_trajectory" in metrics:
        plot_path = save_dir / "flight_telemetry.png"
        plot_episode_telemetry(metrics["sample_trajectory"], save_path=plot_path)
        print(f"  - Telemetry Plot: {plot_path}")

    print("\n" + "=" * 80)
    print(" EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    print(f"  • Episodes Evaluated       : {metrics['n_episodes']}")
    print(f"  • Mean Episode Reward      : {metrics['mean_episode_reward']:.3f} +/- {metrics['reward_std']:.3f}")
    print(f"  • Median Episode Reward    : {metrics['median_episode_reward']:.3f}")
    print(f"  • Mean Original Reward     : {metrics['mean_original_reward']:.3f}")
    print(f"  • Mean Episode Length      : {metrics['mean_episode_length']:.1f} steps")
    print(f"  • Landing Success Rate     : {metrics['landing_success_rate'] * 100:.2f}% ({metrics['success_count']} / {metrics['n_episodes']})")
    print(f"  • Crash Rate               : {metrics['crash_rate'] * 100:.2f}% ({metrics['crash_count']} / {metrics['n_episodes']})")
    print(f"  • Timeout Rate             : {metrics['timeout_rate'] * 100:.2f}% ({metrics['timeout_count']} / {metrics['n_episodes']})")
    print(f"  • Main Engine Usage        : {metrics['main_engine_frequency'] * 100:.2f}% of flight")
    print(f"  • Side Thruster Usage      : {metrics['side_thruster_frequency'] * 100:.2f}% of flight")
    if "saved_json" in metrics:
        print(f"\n Artifacts saved to:")
        print(f"  - Metrics JSON : {metrics['saved_json']}")
        print(f"  - Episodes CSV : {metrics['saved_csv']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
