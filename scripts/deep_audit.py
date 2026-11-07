"""Comprehensive Forensic Audit Script for Stage 5.1.
Verifies all 12 runs, 9,600 episodes, criteria, statistics, and condition categories.
"""

import csv
import json
import math
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import numpy as np
import scipy.stats as stats
import yaml

from evaluation.robustness_evaluation import ROBUSTNESS_TEST_CONDITIONS
from evaluation.evaluate import LandingCriteria

print("=" * 100)
print("AUDIT SECTION 1: VERIFY EXPERIMENTAL DESIGN & ID/OOD CONDITIONS")
print("=" * 100)

# Check benchmark_config.yaml
cfg_path = Path("experiments/benchmark_config.yaml")
with open(cfg_path, "r", encoding="utf-8") as f:
    bench_cfg = yaml.safe_load(f)

print(f"benchmark_config.yaml training timesteps: {bench_cfg['training']['total_timesteps']}")
print(f"benchmark_config.yaml seeds: {bench_cfg['training']['seeds']}")
print(f"benchmark_config.yaml eval episodes: {bench_cfg['evaluation']['episodes_per_condition']}")
print(f"benchmark_config.yaml landing criteria: {bench_cfg['landing_criteria']}")

# Check conditions in ROBUSTNESS_TEST_CONDITIONS
print("\nConditions evaluated in code (ROBUSTNESS_TEST_CONDITIONS):")
for name, p in ROBUSTNESS_TEST_CONDITIONS.items():
    print(f"  {name:25} | category: {p['category']:18} | g={p['gravity']:5.1f} | wind={str(p['enable_wind']):5} | w_power={p['wind_power']:4.1f} | turb={p['turbulence_power']:3.1f}")

# Check Prompt 04 & Prompt 05 history regarding ID vs OOD
print("\nHistory check: In Prompt 04/05 context summary:")
print("Earlier in Prompt 05 summary: 'ID: standard_nominal, moderate_gravity_high, moderate_gravity_low, mild_crosswind_right (4 conditions)'")
print("  and 'OOD: high_wind_cross, extreme_combined, low_gravity_turbulence, high_gravity_turbulence (4 conditions)'")
print("HOWEVER, ROBUSTNESS_TEST_CONDITIONS in evaluation/robustness_evaluation.py was implemented with:")
print(f"  6 in_distribution conditions and 2 out_of_distribution conditions.")

print("\n" + "=" * 100)
print("AUDIT SECTION 2: LANDING CRITERIA COMPARISON")
print("=" * 100)
# Check evaluate.py default LandingCriteria vs benchmark_config.yaml
crit_default = LandingCriteria()
crit_yaml = bench_cfg.get("landing_criteria", {})

print(f"Default LandingCriteria in evaluate.py:")
print(f"  max_pad_offset_x: {crit_default.max_pad_offset_x}")
print(f"  max_touchdown_vx: {crit_default.max_touchdown_vx}")
print(f"  max_touchdown_vy: {crit_default.max_touchdown_vy}")
print(f"  max_touchdown_tilt: {crit_default.max_touchdown_tilt}")
print(f"  max_touchdown_spin: {crit_default.max_touchdown_spin}")
print(f"  require_both_legs: {crit_default.require_both_legs}")

print(f"\nLandingCriteria in experiments/benchmark_config.yaml:")
for k, v in crit_yaml.items():
    print(f"  {k}: {v}")

# Verify what criteria was actually passed to evaluate_robustness in benchmark_runner.py
# In benchmark_runner.py: criteria = LandingCriteria(**crit_cfg) where crit_cfg is bench_cfg['landing_criteria']
print(f"\nExact criteria passed in benchmark_runner.py:")
print(f"  max_touchdown_vx = {crit_yaml.get('max_touchdown_vx', crit_default.max_touchdown_vx)}")
print(f"  max_touchdown_vy = {crit_yaml.get('max_touchdown_vy', crit_default.max_touchdown_vy)}")
print(f"  max_touchdown_spin = {crit_yaml.get('max_touchdown_spin', crit_default.max_touchdown_spin)}")
print(f"  max_touchdown_tilt = {crit_yaml.get('max_touchdown_tilt', crit_default.max_touchdown_tilt)}")
print(f"  max_pad_offset_x = {crit_yaml.get('max_pad_offset_x', crit_default.max_pad_offset_x)}")
print(f"  require_both_legs = {crit_yaml.get('require_both_legs', crit_default.require_both_legs)}")

print("\n" + "=" * 100)
print("AUDIT SECTION 3: VERIFY ALL 12 RUNS, STEPS, AND RAW CSV EPISODE RECORDS")
print("=" * 100)

paradigms = ["A_standard", "B_dr_only", "C_curriculum_only", "D_curriculum_and_dr"]
seeds = [42, 123, 999]

total_episodes_found = 0
total_timesteps_found = 0
run_counts = 0

all_runs_data = {}

for p in paradigms:
    all_runs_data[p] = {}
    for s in seeds:
        m_dir = Path("models/benchmark") / p / f"seed_{s}"
        exp_dir = Path("experiments/benchmark") / p / f"seed_{s}"
        model_file = m_dir / "final_model.zip"
        run_sum_file = exp_dir / "run_summary.json"
        rob_rep_file = exp_dir / "robustness_eval" / "robustness_report.json"
        rob_csv_file = exp_dir / "robustness_eval" / "robustness_episodes.csv"
        
        # Verify model exists
        assert model_file.is_file(), f"Missing model: {model_file}"
        
        # Verify run_summary
        with open(run_sum_file, "r", encoding="utf-8") as f:
            r_sum = json.load(f)
        steps = r_sum.get("completed_timesteps", 0)
        dur = r_sum.get("duration_seconds", 0)
        assert steps == 500000, f"Steps mismatch for {p} seed {s}: {steps}"
        total_timesteps_found += steps
        run_counts += 1
        
        # Verify robustness report
        with open(rob_rep_file, "r", encoding="utf-8") as f:
            rob_rep = json.load(f)
        conds_tested = len(rob_rep.get("conditions", {}))
        assert conds_tested == 8, f"Conditions mismatch for {p} seed {s}: {conds_tested}"
        
        # Verify CSV rows
        with open(rob_csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        row_count = len(rows)
        assert row_count == 800, f"Row count mismatch for {p} seed {s}: {row_count}"
        total_episodes_found += row_count
        
        # Check checkpoints count
        ckpt_dir = m_dir / "checkpoints"
        ckpts = list(ckpt_dir.glob("*.zip"))
        
        all_runs_data[p][s] = {
            "steps": steps,
            "duration": dur,
            "ckpts_count": len(ckpts),
            "episodes": rows,
            "report": rob_rep,
        }
        print(f"  Run {p}_seed{s:3}: steps={steps:,} | dur={dur:6.1f}s | eps={row_count} | ckpts={len(ckpts)} | model_size={model_file.stat().st_size:,} bytes")

print(f"\nTotal completed production runs: {run_counts}")
print(f"Total training timesteps: {total_timesteps_found:,}")
print(f"Total evaluation episodes across matrix: {total_episodes_found:,}")

print("\n" + "=" * 100)
print("AUDIT SECTION 4: TOUCHDOWN STATISTICS - SUCCESSFUL LANDINGS VS ALL EPISODES")
print("=" * 100)

for p in paradigms:
    print(f"\nPARADIGM: {p}")
    # Aggregate over all 3 seeds for Standard_Nominal condition
    nom_all = []
    nom_succ = []
    nom_crash = []
    for s in seeds:
        for ep in all_runs_data[p][s]["episodes"]:
            if ep["condition"] == "Standard_Nominal":
                nom_all.append(ep)
                if ep["outcome"] == "success":
                    nom_succ.append(ep)
                elif ep["outcome"] in ("crash", "out_of_bounds"):
                    nom_crash.append(ep)
    
    n_all = len(nom_all)
    n_succ = len(nom_succ)
    n_crash = len(nom_crash)
    
    print(f"  Standard_Nominal Counts: Total={n_all}, Success={n_succ} ({n_succ/n_all*100:.1f}%), Crash={n_crash} ({n_crash/n_all*100:.1f}%)")
    
    # 1. Terminal stats across ALL episodes (what was in evaluate.py metrics)
    vx_all = [abs(float(e["final_vx"])) for e in nom_all]
    vy_all = [abs(float(e["final_vy"])) for e in nom_all]
    tilt_all = [abs(float(e["final_tilt_rad"])) for e in nom_all]
    spin_all = [abs(float(e["final_spin_rad_s"])) for e in nom_all]
    main_all = [float(e["main_engine_ratio"]) for e in nom_all]
    side_all = [float(e["side_thruster_ratio"]) for e in nom_all]
    
    print(f"  [ALL EPISODES (N={n_all})]:")
    print(f"    mean_vx: {np.mean(vx_all):.4f} | mean_vy: {np.mean(vy_all):.4f} | mean_tilt: {np.mean(tilt_all):.4f} rad ({np.degrees(np.mean(tilt_all)):.1f} deg) | mean_spin: {np.mean(spin_all):.4f} rad/s")
    print(f"    main_duty: {np.mean(main_all)*100:.1f}% | side_duty: {np.mean(side_all)*100:.1f}%")
    
    # 2. Touchdown stats across SUCCESSFUL LANDINGS ONLY
    if n_succ > 0:
        vx_succ = [abs(float(e["final_vx"])) for e in nom_succ]
        vy_succ = [abs(float(e["final_vy"])) for e in nom_succ]
        tilt_succ = [abs(float(e["final_tilt_rad"])) for e in nom_succ]
        spin_succ = [abs(float(e["final_spin_rad_s"])) for e in nom_succ]
        main_succ = [float(e["main_engine_ratio"]) for e in nom_succ]
        side_succ = [float(e["side_thruster_ratio"]) for e in nom_succ]
        print(f"  [SUCCESSFUL TOUCHDOWNS ONLY (N={n_succ})]:")
        print(f"    mean_vx: {np.mean(vx_succ):.4f} | mean_vy: {np.mean(vy_succ):.4f} | mean_tilt: {np.mean(tilt_succ):.4f} rad ({np.degrees(np.mean(tilt_succ)):.1f} deg) | mean_spin: {np.mean(spin_succ):.4f} rad/s")
        print(f"    main_duty: {np.mean(main_succ)*100:.1f}% | side_duty: {np.mean(side_succ)*100:.1f}%")
    else:
        print(f"  [SUCCESSFUL TOUCHDOWNS ONLY (N=0)]: No successful landings.")

print("\n" + "=" * 100)
print("AUDIT SECTION 5: STATISTICAL TESTS RECOMPUTATION & VERIFICATION")
print("=" * 100)

# Check per-seed ID and OOD success rates
id_success = {}
ood_success = {}
id_reward = {}
ood_reward = {}

for p in paradigms:
    id_success[p] = [all_runs_data[p][s]["report"]["in_distribution"]["mean_success_rate"] for s in seeds]
    ood_success[p] = [all_runs_data[p][s]["report"]["out_of_distribution"]["mean_success_rate"] for s in seeds]
    id_reward[p] = [all_runs_data[p][s]["report"]["in_distribution"]["mean_reward"] for s in seeds]
    ood_reward[p] = [all_runs_data[p][s]["report"]["out_of_distribution"]["mean_reward"] for s in seeds]
    
    print(f"\n{p:22}:")
    print(f"  Seeds ID Success:  {[round(x*100, 1) for x in id_success[p]]}% -> Mean={np.mean(id_success[p])*100:.1f}%, Std={np.std(id_success[p], ddof=1)*100:.1f}%")
    print(f"  Seeds OOD Success: {[round(x*100, 1) for x in ood_success[p]]}% -> Mean={np.mean(ood_success[p])*100:.1f}%, Std={np.std(ood_success[p], ddof=1)*100:.1f}%")
    print(f"  Seeds ID Reward:   {[round(x, 1) for x in id_reward[p]]} -> Mean={np.mean(id_reward[p]):.1f}, Std={np.std(id_reward[p], ddof=1):.1f}")
    print(f"  Seeds OOD Reward:  {[round(x, 1) for x in ood_reward[p]]} -> Mean={np.mean(ood_reward[p]):.1f}, Std={np.std(ood_reward[p], ddof=1):.1f}")

# Recompute pairwise paired t-tests
print("\nPairwise Comparisons across all 6 pairs (Matched seeds N=3):")
pairs = [
    ("B_dr_only", "A_standard"),
    ("C_curriculum_only", "A_standard"),
    ("D_curriculum_and_dr", "A_standard"),
    ("C_curriculum_only", "B_dr_only"),
    ("D_curriculum_and_dr", "B_dr_only"),
    ("D_curriculum_and_dr", "C_curriculum_only"),
]

for metric_name, data_dict in [("ID Success", id_success), ("OOD Success", ood_success), ("ID Reward", id_reward), ("OOD Reward", ood_reward)]:
    print(f"\n--- Metric: {metric_name} ---")
    p_results = []
    for pb, pa in pairs:
        a = np.array(data_dict[pa])
        b = np.array(data_dict[pb])
        diff = b - a
        mean_d = float(np.mean(diff))
        std_d = float(np.std(diff, ddof=1))
        t_stat = mean_d / (std_d / math.sqrt(len(diff))) if std_d > 0 else 0.0
        p_val = 2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=len(diff) - 1)) if std_d > 0 else 1.0
        cohens_dz = mean_d / std_d if std_d > 0 else 0.0
        p_results.append((f"{pb}_vs_{pa}", mean_d, std_d, t_stat, p_val, cohens_dz))
    
    # Sort by p-value for Holm-Bonferroni correction across the family of 6 hypotheses
    p_results.sort(key=lambda x: x[4])
    m = len(p_results)
    print(f"{'Comparison':35} | {'Mean Diff':10} | {'t-stat':8} | {'p-raw':8} | {'Holm-Alpha':10} | {'Cohen dz':8} | {'Sig (p<alpha)?'}")
    print("-" * 105)
    for rank, (c_name, m_diff, s_diff, t_s, p_v, dz) in enumerate(p_results):
        alpha_holm = 0.05 / (m - rank)
        is_sig = p_v < alpha_holm
        print(f"{c_name:35} | {m_diff:10.4f} | {t_s:8.4f} | {p_v:8.4f} | {alpha_holm:10.4f} | {dz:8.4f} | {str(is_sig):15}")

print("\n" + "=" * 100)
print("AUDIT COMPLETE")
print("=" * 100)
