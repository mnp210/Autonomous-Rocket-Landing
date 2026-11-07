"""Benchmark Runner for Controlled Training, Statistical Evaluation & Robustness Validation.

Executes the four Stage 4 paradigms across multiple independent random seeds:
  A. Standard PPO (Control)
  B. PPO + Domain Randomization
  C. PPO + Curriculum Learning
  D. PPO + Curriculum Learning + Domain Randomization

Features:
  - Strict hyperparameter and reward invariance across paradigms
  - Resumption support without overwriting existing checkpoints
  - Multi-condition stress evaluation (ID and OOD)
  - 95% Confidence Interval statistical aggregation
  - Automated report generation and publication-ready visualization
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

import yaml

from training.curriculum_trainer import run_curriculum_experiment
from evaluation.evaluate import LandingCriteria
from evaluation.robustness_evaluation import evaluate_robustness, ROBUSTNESS_TEST_CONDITIONS
from evaluation.statistical_analysis import (
    analyze_paradigm_runs,
    perform_comparative_statistical_analysis,
)
from visualization.benchmark_analysis import (
    plot_benchmark_success_rates,
    plot_id_vs_ood_matrix,
    plot_landing_stability_and_effort,
    plot_seed_variance_distribution,
)


def load_benchmark_config(config_path: Union[str, Path] = "experiments/benchmark_config.yaml") -> Dict[str, Any]:
    """Loads benchmark configuration from YAML."""
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_benchmark_matrix(
    config_path: Union[str, Path] = "experiments/benchmark_config.yaml",
    paradigms_to_run: Optional[List[str]] = None,
    seeds_override: Optional[List[int]] = None,
    timesteps_override: Optional[int] = None,
    eval_episodes_override: Optional[int] = None,
    resume: bool = True,
    verbose: int = 1,
) -> Dict[str, Any]:
    """Executes the complete matrix of experimental paradigms across seeds.

    Args:
        config_path: Path to benchmark configuration file.
        paradigms_to_run: Optional subset of paradigms (e.g. ['A_standard', 'D_curriculum_and_dr']).
        seeds_override: Optional list of random seeds to test.
        timesteps_override: Optional override for training timesteps.
        eval_episodes_override: Optional override for evaluation episodes.
        resume: Skip training if final_model.zip exists.
        verbose: Verbosity level.

    Returns:
        Master dictionary containing benchmark summaries, statistical tests, and artifacts.
    """
    cfg = load_benchmark_config(config_path)

    all_paradigms = cfg.get("experiment_paradigms", {})
    selected_paradigms = (
        {k: all_paradigms[k] for k in paradigms_to_run if k in all_paradigms}
        if paradigms_to_run
        else all_paradigms
    )

    train_cfg = cfg.get("training", {})
    eval_cfg = cfg.get("evaluation", {})
    crit_cfg = cfg.get("landing_criteria", {})
    paths_cfg = cfg.get("paths", {})

    seeds = seeds_override or train_cfg.get("seeds", [42, 123, 999])
    total_timesteps = timesteps_override if timesteps_override is not None else train_cfg.get("total_timesteps", 500000)
    eval_episodes = eval_episodes_override if eval_episodes_override is not None else eval_cfg.get("episodes_per_condition", 100)
    reward_strategy = train_cfg.get("reward_strategy", "baseline")

    criteria = LandingCriteria(**crit_cfg)

    benchmark_root = Path(paths_cfg.get("experiments_dir", "experiments/benchmark"))
    benchmark_root.mkdir(parents=True, exist_ok=True)

    if verbose > 0:
        print("=" * 80)
        print(" LAUNCHING RIGOROUS BENCHMARK EXPERIMENT MATRIX")
        print("=" * 80)
        print(f" Paradigms to Test  : {list(selected_paradigms.keys())}")
        print(f" Independent Seeds  : {seeds}")
        print(f" Timesteps per Run  : {total_timesteps:,}")
        print(f" Eval Episodes/Cond : {eval_episodes}")
        print(f" Fixed Reward Mode  : {reward_strategy}")
        print(f" Resumption Enabled : {resume}")
        print(f" Benchmark Artifacts: {benchmark_root}")
        print("=" * 80)

    paradigm_seed_reports: Dict[str, List[Dict[str, Any]]] = {}
    completed_runs_meta: List[Dict[str, Any]] = []

    for p_key, p_info in selected_paradigms.items():
        p_type = p_info["type"]
        p_name = p_info["name"]
        paradigm_seed_reports[p_key] = []

        for seed in seeds:
            run_tag = f"{p_key}_seed{seed}"
            model_dir = Path(paths_cfg.get("models_dir", "models/benchmark")) / p_key / f"seed_{seed}"
            log_dir = Path(paths_cfg.get("logs_dir", "logs/benchmark")) / p_key / f"seed_{seed}"
            exp_dir = Path(paths_cfg.get("experiments_dir", "experiments/benchmark")) / p_key / f"seed_{seed}"
            model_dir.mkdir(parents=True, exist_ok=True)
            exp_dir.mkdir(parents=True, exist_ok=True)
            log_dir.mkdir(parents=True, exist_ok=True)

            final_model = model_dir / "final_model.zip"
            run_summary_path = exp_dir / "run_summary.json"

            if verbose > 0:
                print(f"\n>>> PARADIGM: {p_name} | SEED: {seed} | TAG: {run_tag}")

            # Verify genuine completion (prevent 256-step smoke runs or aborted runs from masquerading as completed)
            is_completed = False
            s_data: Dict[str, Any] = {}
            if final_model.is_file() and run_summary_path.is_file():
                try:
                    with open(run_summary_path, "r", encoding="utf-8") as f:
                        s_data = json.load(f)
                    completed_steps = s_data.get("completed_timesteps", s_data.get("total_timesteps", 0))
                    if completed_steps >= total_timesteps:
                        is_completed = True
                except Exception:
                    is_completed = False

            if resume and is_completed:
                if verbose > 0:
                    dur = s_data.get("duration_seconds", 0)
                    print(f"    [RESUME] Found verified completed model ({total_timesteps:,} steps, duration: {dur:.1f}s) at: {final_model}. Skipping training.")
                train_meta = dict(s_data)
                train_meta["final_model_path"] = str(final_model)
                train_meta["status"] = "resumed_from_disk"
            else:
                if verbose > 0 and final_model.is_file() and not is_completed:
                    print(f"    [RETRAIN] Existing checkpoint did not satisfy target budget ({total_timesteps:,} steps). Retraining.")
                train_meta = run_curriculum_experiment(
                    experiment_type=p_type,
                    ppo_config_path=train_cfg.get("ppo_config_path", "configs/ppo_config.yaml"),
                    curriculum_config_path=train_cfg.get("curriculum_config_path", "configs/curriculum.yaml"),
                    dr_config_path=train_cfg.get("dr_config_path", "configs/domain_randomization.yaml"),
                    reward_strategy=reward_strategy,
                    total_timesteps=total_timesteps,
                    seed=seed,
                    run_id=f"benchmark_{run_tag}",
                    verbose=0,
                    custom_model_dir=model_dir,
                    custom_log_dir=log_dir,
                    custom_exp_dir=exp_dir,
                )
                train_meta["status"] = "newly_trained"

            completed_runs_meta.append(train_meta)

            # Evaluate model across all stress conditions
            eval_out_dir = exp_dir / "robustness_eval"
            eval_out_dir.mkdir(parents=True, exist_ok=True)
            robustness_json = eval_out_dir / "robustness_report.json"

            eval_completed = False
            if resume and robustness_json.is_file():
                try:
                    with open(robustness_json, "r", encoding="utf-8") as f:
                        cached_eval = json.load(f)
                    if cached_eval.get("episodes_per_condition", 0) >= eval_episodes:
                        eval_report = cached_eval
                        eval_completed = True
                        if verbose > 0:
                            print(f"    [RESUME] Found completed robustness evaluation ({eval_episodes} eps/cond).")
                except Exception:
                    eval_completed = False

            if not eval_completed:
                eval_report = evaluate_robustness(
                    model_path=train_meta["final_model_path"],
                    episodes_per_condition=eval_episodes,
                    output_dir=eval_out_dir,
                    seed=eval_cfg.get("eval_seed_base", 5000) + seed,
                    criteria=criteria,
                )

            eval_report["seed"] = seed
            eval_report["paradigm"] = p_key
            paradigm_seed_reports[p_key].append(eval_report)

            if verbose > 0:
                id_rate = eval_report["in_distribution"]["mean_success_rate"] * 100
                ood_rate = eval_report["out_of_distribution"]["mean_success_rate"] * 100
                print(f"    [EVAL COMPLETE] ID Success: {id_rate:5.1f}% | OOD Success: {ood_rate:5.1f}%")

    # Perform statistical aggregation and confidence interval computation
    paradigm_analyses: Dict[str, Dict[str, Any]] = {}
    for p_key, reports in paradigm_seed_reports.items():
        paradigm_analyses[p_key] = analyze_paradigm_runs(p_key, reports)

    # Perform pairwise hypothesis tests
    statistical_comparisons = perform_comparative_statistical_analysis(paradigm_analyses)

    # Generate figures
    plots_dir = benchmark_root / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    fig1 = plot_benchmark_success_rates(paradigm_analyses, save_path=plots_dir / "benchmark_success_rates.png")
    fig2 = plot_id_vs_ood_matrix(paradigm_analyses, save_path=plots_dir / "id_vs_ood_matrix.png")
    fig3 = plot_landing_stability_and_effort(paradigm_analyses, save_path=plots_dir / "landing_stability_effort.png")
    fig4 = plot_seed_variance_distribution(paradigm_analyses, save_path=plots_dir / "seed_variance_distribution.png")

    # Export master benchmark summary
    benchmark_summary = {
        "timestamp": datetime.now().isoformat(),
        "total_timesteps_per_run": total_timesteps,
        "eval_episodes_per_condition": eval_episodes,
        "seeds": seeds,
        "reward_strategy": reward_strategy,
        "landing_criteria": crit_cfg,
        "completed_runs": completed_runs_meta,
        "paradigm_statistical_analyses": paradigm_analyses,
        "pairwise_hypothesis_tests": statistical_comparisons,
        "generated_plots": [str(fig1), str(fig2), str(fig3), str(fig4)],
    }

    is_smoke = bool(total_timesteps < 10000)
    summary_filename = "smoke_benchmark_summary.json" if is_smoke else "production_benchmark_summary.json"
    summary_json_path = benchmark_root / summary_filename
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)

    # Also maintain canonical benchmark_summary.json
    with open(benchmark_root / "benchmark_summary.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)

    if verbose > 0:
        print("\n" + "=" * 80)
        print(" BENCHMARK COMPLETED SUCCESSFULLY")
        print(f" Master Report JSON: {summary_json_path}")
        print(f" Generated Plots   : {plots_dir}")
        print("=" * 80)

    return benchmark_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Rocket Landing Benchmark Runner")
    parser.add_argument("--config", type=str, default="experiments/benchmark_config.yaml", help="Path to benchmark config")
    parser.add_argument("--timesteps", type=int, default=None, help="Override training timesteps")
    parser.add_argument("--eval-episodes", type=int, default=None, help="Override evaluation episodes per condition")
    parser.add_argument("--paradigms", nargs="+", default=None, help="Specific paradigms to run")
    parser.add_argument("--seeds", nargs="+", type=int, default=None, help="Specific random seeds")
    parser.add_argument("--no-resume", action="store_true", help="Force retraining without resume")

    args = parser.parse_args()

    run_benchmark_matrix(
        config_path=args.config,
        paradigms_to_run=args.paradigms,
        seeds_override=args.seeds,
        timesteps_override=args.timesteps,
        eval_episodes_override=args.eval_episodes,
        resume=not args.no_resume,
        verbose=1,
    )
