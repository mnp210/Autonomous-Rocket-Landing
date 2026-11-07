"""Robustness evaluation harness for autonomous rocket landing policies.

Benchmarks policy generalizability across structured environmental stress conditions:
  - Nominal standard conditions (Control)
  - Low gravity (e.g. Moon / Mars analogue)
  - Heavy gravity
  - Calm vs moderate vs severe aerodynamic wind
  - High rotational turbulence
  - Out-of-Distribution (OOD) extreme multi-stressor combinations

Calculates landing success, crash, touchdown velocities, angles, and thruster duty cycles.
Separates In-Distribution (ID) and Out-of-Distribution (OOD) performance.
"""

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import gymnasium as gym
import numpy as np
from stable_baselines3 import PPO

from environments.env_loader import make_environment
from environments.domain_randomization import DomainRandomizationConfig
from evaluation.evaluate import evaluate_policy, LandingCriteria


# Canonical environmental stress test matrix
ROBUSTNESS_TEST_CONDITIONS: Dict[str, Dict[str, Any]] = {
    # In-Distribution (ID) Benchmark Suites
    "Standard_Nominal": {
        "category": "in_distribution",
        "description": "Standard nominal LunarLander physics (-10 m/s^2 gravity, zero wind)",
        "gravity": -10.0,
        "enable_wind": False,
        "wind_power": 0.0,
        "turbulence_power": 0.0,
    },
    "Low_Gravity": {
        "category": "in_distribution",
        "description": "Reduced gravity (-7.5 m/s^2) simulating low-density celestial bodies",
        "gravity": -7.5,
        "enable_wind": False,
        "wind_power": 0.0,
        "turbulence_power": 0.0,
    },
    "Heavy_Gravity": {
        "category": "in_distribution",
        "description": "Accelerated gravity (-12.5 m/s^2) requiring heightened upward thrust",
        "gravity": -12.5,
        "enable_wind": False,
        "wind_power": 0.0,
        "turbulence_power": 0.0,
    },
    "Moderate_Wind": {
        "category": "in_distribution",
        "description": "Nominal gravity with persistent 15.0 m/s crosswind gusts",
        "gravity": -10.0,
        "enable_wind": True,
        "wind_power": 15.0,
        "turbulence_power": 1.0,
    },
    "Strong_Wind": {
        "category": "in_distribution",
        "description": "Nominal gravity with severe 22.0 m/s crosswind gusts",
        "gravity": -10.0,
        "enable_wind": True,
        "wind_power": 22.0,
        "turbulence_power": 1.5,
    },
    "High_Turbulence": {
        "category": "in_distribution",
        "description": "Nominal gravity with rotational atmospheric turbulence (2.5)",
        "gravity": -10.0,
        "enable_wind": True,
        "wind_power": 12.0,
        "turbulence_power": 2.5,
    },

    # Out-of-Distribution (OOD) Stress Suites
    "OOD_Extreme_Combined": {
        "category": "out_of_distribution",
        "description": "Severe heavy gravity (-15.0 m/s^2) combined with hurricane-level wind (30.0) and severe turbulence (3.5)",
        "gravity": -15.0,
        "enable_wind": True,
        "wind_power": 30.0,
        "turbulence_power": 3.5,
    },
    "OOD_Microgravity_Shear": {
        "category": "out_of_distribution",
        "description": "Extremely weak gravity (-4.5 m/s^2) with violent lateral shear wind (28.0)",
        "gravity": -4.5,
        "enable_wind": True,
        "wind_power": 28.0,
        "turbulence_power": 3.0,
    },
}


def build_fixed_stress_environment(
    condition_params: Dict[str, Any],
    seed: int = 42,
) -> gym.Env:
    """Builds a test environment with fixed physical parameters for reproducibility."""
    dr_cfg = DomainRandomizationConfig(
        enabled=True,
        mode="fixed",
        fixed_gravity=condition_params["gravity"],
        fixed_enable_wind=condition_params["enable_wind"],
        fixed_wind_power=condition_params["wind_power"],
        fixed_turbulence_power=condition_params["turbulence_power"],
    )
    return make_environment(
        env_id="LunarLander-v3",
        seed=seed,
        domain_randomization_config=dr_cfg,
    )


def evaluate_robustness(
    model_path: Union[str, Path],
    episodes_per_condition: int = 25,
    conditions: Optional[Dict[str, Dict[str, Any]]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    seed: int = 1000,
    criteria: Optional[LandingCriteria] = None,
) -> Dict[str, Any]:
    """Evaluates a saved PPO policy against the entire matrix of stress conditions.

    Args:
        model_path: Path to trained PPO model archive (.zip).
        episodes_per_condition: Number of rollout episodes per test condition.
        conditions: Custom condition dictionary (defaults to ROBUSTNESS_TEST_CONDITIONS).
        output_dir: Output folder to write JSON summary and CSV records.
        seed: Base random seed for evaluation.
        criteria: Optional physical landing criteria.

    Returns:
        Structured evaluation dictionary categorized into ID and OOD statistics.
    """
    model_path = Path(model_path)
    if not model_path.is_file() and not model_path.with_suffix(".zip").is_file():
        raise FileNotFoundError(f"Policy model not found: {model_path}")

    model = PPO.load(str(model_path))
    matrix = conditions or ROBUSTNESS_TEST_CONDITIONS

    condition_summaries: Dict[str, Dict[str, Any]] = {}
    all_episode_records: List[Dict[str, Any]] = []

    id_success_rates = []
    id_mean_rewards = []
    ood_success_rates = []
    ood_mean_rewards = []

    for name, params in matrix.items():
        category = params.get("category", "in_distribution")
        test_env = build_fixed_stress_environment(params, seed=seed)

        metrics, records = evaluate_policy(
            model=model,
            env=test_env,
            n_episodes=episodes_per_condition,
            deterministic=True,
            seed=seed,
            criteria=criteria,
        )
        test_env.close()

        for rec in records:
            rec["condition"] = name
            rec["category"] = category
            all_episode_records.append(rec)

        summary_entry = {
            "condition": name,
            "category": category,
            "description": params.get("description", ""),
            "parameters": {
                "gravity": params["gravity"],
                "enable_wind": params["enable_wind"],
                "wind_power": params["wind_power"],
                "turbulence_power": params["turbulence_power"],
            },
            "metrics": metrics,
        }
        condition_summaries[name] = summary_entry

        if category == "in_distribution":
            id_success_rates.append(metrics["landing_success_rate"])
            id_mean_rewards.append(metrics["mean_episode_reward"])
        else:
            ood_success_rates.append(metrics["landing_success_rate"])
            ood_mean_rewards.append(metrics["mean_episode_reward"])

    # High-level aggregate scorecard
    scorecard = {
        "model_path": str(model_path),
        "episodes_per_condition": episodes_per_condition,
        "total_conditions_tested": len(matrix),
        "in_distribution": {
            "mean_success_rate": round(float(np.mean(id_success_rates)), 4) if id_success_rates else 0.0,
            "mean_reward": round(float(np.mean(id_mean_rewards)), 2) if id_mean_rewards else 0.0,
        },
        "out_of_distribution": {
            "mean_success_rate": round(float(np.mean(ood_success_rates)), 4) if ood_success_rates else 0.0,
            "mean_reward": round(float(np.mean(ood_mean_rewards)), 2) if ood_mean_rewards else 0.0,
        },
        "conditions": condition_summaries,
    }

    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        json_file = out_dir / "robustness_report.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(scorecard, f, indent=2)

        csv_file = out_dir / "robustness_episodes.csv"
        if all_episode_records:
            fieldnames = list(all_episode_records[0].keys())
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_episode_records)

        scorecard["saved_json"] = str(json_file)
        scorecard["saved_csv"] = str(csv_file)

    return scorecard


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Robustness of Trained Rocket Landing Policies")
    parser.add_argument("--model-path", type=str, required=True, help="Path to model archive (.zip)")
    parser.add_argument("--episodes", type=int, default=20, help="Episodes to evaluate per stress condition")
    parser.add_argument("--output-dir", type=str, default=None, help="Output folder to write results")
    parser.add_argument("--seed", type=int, default=42, help="Evaluation random seed")

    args = parser.parse_args()

    out = args.output_dir or Path(args.model_path).parent / "robustness_results"
    results = evaluate_robustness(
        model_path=args.model_path,
        episodes_per_condition=args.episodes,
        output_dir=out,
        seed=args.seed,
    )

    print("=" * 80)
    print(" ROBUSTNESS EVALUATION REPORT")
    print("=" * 80)
    print(f" Model Evaluated   : {args.model_path}")
    print(f" ID Success Rate   : {results['in_distribution']['mean_success_rate']*100:.2f}% (Mean Reward: {results['in_distribution']['mean_reward']:.1f})")
    print(f" OOD Success Rate  : {results['out_of_distribution']['mean_success_rate']*100:.2f}% (Mean Reward: {results['out_of_distribution']['mean_reward']:.1f})")
    print("-" * 80)
    for c_name, c_data in results["conditions"].items():
        m = c_data["metrics"]
        print(f"  [{c_data['category'][:3].upper()}] {c_name:<24} | Success: {m['landing_success_rate']*100:>5.1f}% | Crash: {m['crash_rate']*100:>5.1f}% | Reward: {m['mean_episode_reward']:>7.1f}")
    print("=" * 80)
