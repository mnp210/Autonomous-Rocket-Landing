"""Statistical analysis module for autonomous rocket landing benchmarks.

Provides rigorous sample statistics, 95% Student's t confidence intervals,
In-Distribution (ID) vs Out-of-Distribution (OOD) aggregates, and pairwise
hypothesis testing across independent training seeds.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import scipy.stats as stats


@dataclass
class ConfidenceInterval:
    """Statistical summary containing mean, std, sample size, and 95% CI bounds."""
    mean: float
    std: float
    sample_size: int
    confidence_level: float
    margin_of_error: float
    lower_bound: float
    upper_bound: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_confidence_interval(
    data: Union[List[float], np.ndarray],
    confidence: float = 0.95,
) -> ConfidenceInterval:
    """Computes sample mean, standard deviation, and Student's t confidence interval.

    Args:
        data: Sequence of numeric values across random seeds.
        confidence: Desired confidence level (default 0.95 for 95% CI).

    Returns:
        ConfidenceInterval dataclass.
    """
    arr = np.array(data, dtype=np.float64)
    n = len(arr)

    if n == 0:
        return ConfidenceInterval(
            mean=0.0, std=0.0, sample_size=0, confidence_level=confidence,
            margin_of_error=0.0, lower_bound=0.0, upper_bound=0.0,
        )

    mean_val = float(np.mean(arr))

    if n == 1:
        return ConfidenceInterval(
            mean=round(mean_val, 4),
            std=0.0,
            sample_size=1,
            confidence_level=confidence,
            margin_of_error=0.0,
            lower_bound=round(mean_val, 4),
            upper_bound=round(mean_val, 4),
        )

    std_val = float(np.std(arr, ddof=1))
    se = std_val / np.sqrt(n)

    # Student's t critical value for small sample sizes
    alpha = 1.0 - confidence
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=n - 1))
    margin = float(t_crit * se)

    return ConfidenceInterval(
        mean=round(mean_val, 4),
        std=round(std_val, 4),
        sample_size=n,
        confidence_level=confidence,
        margin_of_error=round(margin, 4),
        lower_bound=round(mean_val - margin, 4),
        upper_bound=round(mean_val + margin, 4),
    )


def compute_paired_t_test(
    sample_a: Union[List[float], np.ndarray],
    sample_b: Union[List[float], np.ndarray],
) -> Dict[str, Any]:
    """Calculates Paired Student's t-test for matched seeds and Cohen's dz effect size.

    Args:
        sample_a: Observations from Paradigm A (matched by seed).
        sample_b: Observations from Paradigm B (matched by seed).

    Returns:
        Dictionary with t_statistic, p_value, mean_difference, cohens_dz, and 95% CI of difference.
    """
    a = np.array(sample_a, dtype=np.float64)
    b = np.array(sample_b, dtype=np.float64)

    if len(a) != len(b):
        raise ValueError(f"Paired t-test requires identical sample sizes, got len(a)={len(a)}, len(b)={len(b)}")

    n = len(a)
    if n < 2:
        return {
            "test_type": "Paired Student's t-test",
            "sample_size": n,
            "t_statistic": 0.0,
            "p_value": 1.0,
            "significant_p05": False,
            "mean_difference": round(float(np.mean(b) - np.mean(a)), 4) if n > 0 else 0.0,
            "cohens_d": 0.0,
            "note": "Insufficient paired seed sample size (N < 2)",
        }

    diffs = b - a
    mean_diff = float(np.mean(diffs))
    var_diff = float(np.var(diffs, ddof=1))
    std_diff = np.sqrt(var_diff) if var_diff > 0 else 0.0

    if std_diff == 0.0:
        return {
            "test_type": "Paired Student's t-test",
            "sample_size": n,
            "t_statistic": 0.0,
            "p_value": 1.0 if mean_diff == 0.0 else 0.0,
            "significant_p05": False,
            "mean_difference": round(mean_diff, 4),
            "cohens_d": 0.0,
            "ci_95_difference": [round(mean_diff, 4), round(mean_diff, 4)],
            "note": "Zero difference variance across paired seeds",
        }

    res = stats.ttest_rel(b, a)
    t_stat = float(res.statistic) if np.isfinite(res.statistic) else 0.0
    p_val = float(res.pvalue) if np.isfinite(res.pvalue) else 1.0
    cohens_dz = float(mean_diff / std_diff)

    # 95% CI of paired difference
    t_crit = float(stats.t.ppf(0.975, df=n - 1))
    margin = float(t_crit * (std_diff / np.sqrt(n)))

    return {
        "test_type": "Paired Student's t-test",
        "sample_size": n,
        "t_statistic": round(t_stat, 4),
        "p_value": round(p_val, 6),
        "significant_p05": bool(p_val < 0.05),
        "mean_difference": round(mean_diff, 4),
        "cohens_d": round(cohens_dz, 4),
        "ci_95_difference": [round(mean_diff - margin, 4), round(mean_diff + margin, 4)],
        "note": "Paired Student's t-test across matched seeds",
    }


def compute_welch_t_test(
    sample_a: Union[List[float], np.ndarray],
    sample_b: Union[List[float], np.ndarray],
) -> Dict[str, Any]:
    """Calculates Welch's two-sample t-test (unequal variances assumed) and Cohen's d.

    Args:
        sample_a: Performance observations from Paradigm A.
        sample_b: Performance observations from Paradigm B.

    Returns:
        Dictionary with t_statistic, p_value, mean_difference, cohens_d, and significance flag.
    """
    a = np.array(sample_a, dtype=np.float64)
    b = np.array(sample_b, dtype=np.float64)

    if len(a) < 2 or len(b) < 2:
        return {
            "test_type": "Welch's two-sample t-test",
            "t_statistic": 0.0,
            "p_value": 1.0,
            "significant_p05": False,
            "mean_difference": round(float(np.mean(b) - np.mean(a)), 4) if (len(a) and len(b)) else 0.0,
            "cohens_d": 0.0,
            "note": "Insufficient seed sample size (N < 2 per group) for formal Welch t-test",
        }

    diff = float(np.mean(b) - np.mean(a))
    var_a = float(np.var(a, ddof=1))
    var_b = float(np.var(b, ddof=1))

    # Pooled standard deviation for Cohen's d
    s_pooled = np.sqrt(((len(a) - 1) * var_a + (len(b) - 1) * var_b) / (len(a) + len(b) - 2)) if (var_a + var_b) > 0 else 0.0
    cohens_d = float(diff / s_pooled) if s_pooled > 0 else 0.0

    # If both arrays have zero variance (e.g. all 0.0)
    if var_a == 0.0 and var_b == 0.0:
        return {
            "test_type": "Welch's two-sample t-test",
            "t_statistic": 0.0,
            "p_value": 1.0 if diff == 0.0 else 0.0,
            "significant_p05": False,
            "mean_difference": round(diff, 4),
            "cohens_d": 0.0,
            "note": "Zero sample variance in both groups",
        }

    res = stats.ttest_ind(b, a, equal_var=False)
    p_val = float(res.pvalue) if np.isfinite(res.pvalue) else 1.0
    t_stat = float(res.statistic) if np.isfinite(res.statistic) else 0.0

    return {
        "test_type": "Welch's two-sample t-test",
        "t_statistic": round(t_stat, 4),
        "p_value": round(p_val, 6),
        "significant_p05": bool(p_val < 0.05),
        "mean_difference": round(diff, 4),
        "cohens_d": round(cohens_d, 4),
        "note": "Welch's two-sample t-test (unpaired independent assumption)",
    }


def analyze_paradigm_runs(
    paradigm_label: str,
    seed_reports: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregates multi-seed evaluation reports for a single experimental paradigm.

    Args:
        paradigm_label: Identifier (e.g. 'A_standard' or 'D_curriculum_and_dr').
        seed_reports: List of robustness reports (one per seed).

    Returns:
        Structured dictionary with condition-level and ID/OOD 95% confidence intervals.
    """
    if not seed_reports:
        return {"paradigm": paradigm_label, "num_seeds": 0}

    num_seeds = len(seed_reports)
    first_report = seed_reports[0]
    condition_names = list(first_report["conditions"].keys())

    condition_stats: Dict[str, Any] = {}
    id_overall_successes: List[float] = []
    ood_overall_successes: List[float] = []
    id_overall_rewards: List[float] = []
    ood_overall_rewards: List[float] = []

    for c_name in condition_names:
        c_category = first_report["conditions"][c_name]["category"]

        # Collect metrics across seeds for this condition
        succ_rates = [rep["conditions"][c_name]["metrics"]["landing_success_rate"] for rep in seed_reports]
        rewards = [rep["conditions"][c_name]["metrics"]["mean_episode_reward"] for rep in seed_reports]
        crashes = [rep["conditions"][c_name]["metrics"]["crash_rate"] for rep in seed_reports]
        timeouts = [rep["conditions"][c_name]["metrics"]["timeout_rate"] for rep in seed_reports]
        vx_list = [rep["conditions"][c_name]["metrics"]["mean_landing_vx"] for rep in seed_reports]
        vy_list = [rep["conditions"][c_name]["metrics"]["mean_landing_vy"] for rep in seed_reports]
        tilts = [rep["conditions"][c_name]["metrics"]["mean_absolute_tilt_rad"] for rep in seed_reports]
        spins = [rep["conditions"][c_name]["metrics"]["mean_absolute_spin_rad_s"] for rep in seed_reports]
        main_duties = [rep["conditions"][c_name]["metrics"]["main_engine_frequency"] for rep in seed_reports]
        side_duties = [rep["conditions"][c_name]["metrics"]["side_thruster_frequency"] for rep in seed_reports]

        condition_stats[c_name] = {
            "category": c_category,
            "success_rate_ci": compute_confidence_interval(succ_rates).to_dict(),
            "mean_reward_ci": compute_confidence_interval(rewards).to_dict(),
            "crash_rate_ci": compute_confidence_interval(crashes).to_dict(),
            "timeout_rate_ci": compute_confidence_interval(timeouts).to_dict(),
            "mean_landing_vx_ci": compute_confidence_interval(vx_list).to_dict(),
            "mean_landing_vy_ci": compute_confidence_interval(vy_list).to_dict(),
            "mean_tilt_rad_ci": compute_confidence_interval(tilts).to_dict(),
            "mean_spin_rad_s_ci": compute_confidence_interval(spins).to_dict(),
            "main_engine_frequency_ci": compute_confidence_interval(main_duties).to_dict(),
            "side_thruster_frequency_ci": compute_confidence_interval(side_duties).to_dict(),
        }

    # Aggregate ID and OOD averages per seed
    for rep in seed_reports:
        id_overall_successes.append(rep["in_distribution"]["mean_success_rate"])
        ood_overall_successes.append(rep["out_of_distribution"]["mean_success_rate"])
        id_overall_rewards.append(rep["in_distribution"]["mean_reward"])
        ood_overall_rewards.append(rep["out_of_distribution"]["mean_reward"])

    return {
        "paradigm": paradigm_label,
        "num_seeds": num_seeds,
        "in_distribution": {
            "success_rate_ci": compute_confidence_interval(id_overall_successes).to_dict(),
            "mean_reward_ci": compute_confidence_interval(id_overall_rewards).to_dict(),
            "raw_seed_successes": id_overall_successes,
            "raw_seed_rewards": id_overall_rewards,
        },
        "out_of_distribution": {
            "success_rate_ci": compute_confidence_interval(ood_overall_successes).to_dict(),
            "mean_reward_ci": compute_confidence_interval(ood_overall_rewards).to_dict(),
            "raw_seed_successes": ood_overall_successes,
            "raw_seed_rewards": ood_overall_rewards,
        },
        "conditions": condition_stats,
    }


def perform_comparative_statistical_analysis(
    paradigm_analyses: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Performs pairwise hypothesis tests between experimental paradigms.

    Includes both Paired Student's t-test (accounting for identical seed blocking)
    and Welch's two-sample t-test (unpaired reference), accompanied by effect sizes
    and multiple-comparison metadata.
    """
    comparisons: Dict[str, Any] = {}

    keys = list(paradigm_analyses.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            name_a = keys[i]
            name_b = keys[j]
            data_a = paradigm_analyses[name_a]
            data_b = paradigm_analyses[name_b]

            pair_key = f"{name_b}_vs_{name_a}"
            comparisons[pair_key] = {
                # Matched-seed Paired t-tests (Recommended for identical seed blocks)
                "paired_id_success": compute_paired_t_test(
                    data_a["in_distribution"]["raw_seed_successes"],
                    data_b["in_distribution"]["raw_seed_successes"],
                ),
                "paired_ood_success": compute_paired_t_test(
                    data_a["out_of_distribution"]["raw_seed_successes"],
                    data_b["out_of_distribution"]["raw_seed_successes"],
                ),
                "paired_id_reward": compute_paired_t_test(
                    data_a["in_distribution"]["raw_seed_rewards"],
                    data_b["in_distribution"]["raw_seed_rewards"],
                ),
                "paired_ood_reward": compute_paired_t_test(
                    data_a["out_of_distribution"]["raw_seed_rewards"],
                    data_b["out_of_distribution"]["raw_seed_rewards"],
                ),
                # Independent Welch t-tests (Unpaired reference)
                "in_distribution_success_test": compute_welch_t_test(
                    data_a["in_distribution"]["raw_seed_successes"],
                    data_b["in_distribution"]["raw_seed_successes"],
                ),
                "out_of_distribution_success_test": compute_welch_t_test(
                    data_a["out_of_distribution"]["raw_seed_successes"],
                    data_b["out_of_distribution"]["raw_seed_successes"],
                ),
                "in_distribution_reward_test": compute_welch_t_test(
                    data_a["in_distribution"]["raw_seed_rewards"],
                    data_b["in_distribution"]["raw_seed_rewards"],
                ),
                "out_of_distribution_reward_test": compute_welch_t_test(
                    data_a["out_of_distribution"]["raw_seed_rewards"],
                    data_b["out_of_distribution"]["raw_seed_rewards"],
                ),
            }

    # Apply Holm-Bonferroni step-down correction to paired tests
    total_comparisons = len(comparisons)
    if total_comparisons > 0:
        for metric_key in ["paired_id_success", "paired_ood_success", "paired_id_reward", "paired_ood_reward"]:
            p_vals = [(pk, comparisons[pk][metric_key]["p_value"]) for pk in comparisons]
            p_vals.sort(key=lambda x: x[1])
            running_max = 0.0
            for rank, (pk, p_raw) in enumerate(p_vals):
                multiplier = total_comparisons - rank
                adjusted_alpha = 0.05 / multiplier
                adj_p = min(1.0, max(running_max, p_raw * multiplier))
                running_max = adj_p
                comparisons[pk][metric_key]["holm_bonferroni_alpha"] = round(adjusted_alpha, 6)
                comparisons[pk][metric_key]["holm_adjusted_p_value"] = round(adj_p, 6)
                comparisons[pk][metric_key]["significant_holm_bonferroni"] = bool(adj_p < 0.05)

    return comparisons
