/**
 * Forensic Reconciled Benchmark Dataset for the Autonomous Rocket Landing Study.
 *
 * Sourced directly from:
 * - experiments/benchmark/production_benchmark_summary.json
 * - 12 raw CSV runs (experiments/benchmark/{paradigm}/seed_{seed}/robustness_eval/robustness_episodes.csv)
 * - docs/benchmark_results.md
 *
 * Total Scope: 12 Production Runs (4 Paradigms × 3 Seeds: 42, 123, 999),
 * 6,000,000 Training Steps, 9,600 Evaluation Episodes.
 */

export interface ConfidenceInterval {
  mean: number;
  std: number;
  sample_size: number;
  confidence_level: number;
  margin_of_error: number;
  lower_bound: number;
  upper_bound: number;
}

export interface OutcomeCounts {
  success: number;
  crash: number;
  timeout: number;
  out_of_bounds: number;
  total: number;
}

export interface ConditionBenchmark {
  condition: string;
  category: 'in_distribution' | 'out_of_distribution';
  gravity: number;
  wind: number;
  turbulence: number;
  outcomes: OutcomeCounts;
  success_rate: number;
  mean_reward: number;
  mean_resting_tilt_deg?: number | null;
  resting_tilt_sample_size?: number;
  resting_tilt_caveat?: string;
}

export interface ParadigmData {
  id: string;
  name: string;
  description: string;
  training_protocol: string;
  seeds: number[];
  timesteps_per_run: number;
  total_eval_episodes: number;
  nominal_outcomes: OutcomeCounts;
  nominal_success_rate: number;
  id_outcomes: OutcomeCounts;
  id_success_rate: number;
  ood_outcomes: OutcomeCounts;
  ood_success_rate: number;
  overall_outcomes: OutcomeCounts;
  overall_success_rate: number;
  nominal_resting_tilt_deg: number;
  nominal_resting_sample_size: number;
  nominal_resting_caveat?: string;
  terminal_vx: number;
  terminal_vy: number;
  main_engine_duty: number;
  side_thruster_duty: number;
  success_rate_ci: ConfidenceInterval;
  mean_reward_ci: ConfidenceInterval;
  conditions: Record<string, ConditionBenchmark>;
}

export interface PairwiseTestResult {
  comparison: string;
  pair_label: string;
  t_statistic: number;
  raw_p_value: number;
  holm_multiplier: number;
  holm_alpha: number;
  holm_adjusted_p_value: number;
  cohens_d: number;
  mean_difference: number;
  significant: boolean;
  verdict: string;
}

export function computeWilsonScoreInterval(k: number, n: number, confidence: number = 0.95): { point: number; lower: number; upper: number } {
  if (n <= 0) return { point: 0, lower: 0, upper: 0 };
  const z = confidence === 0.99 ? 2.576 : confidence === 0.90 ? 1.645 : 1.96;
  const p = k / n;
  const z2 = z * z;
  const center = (k + z2 / 2) / (n + z2);
  const factor = (z / (n + z2)) * Math.sqrt((k * (n - k)) / n + z2 / 4);
  const lower = Math.max(0, (center - factor) * 100);
  const upper = Math.min(100, (center + factor) * 100);
  return { point: p * 100, lower, upper };
}

export const EVALUATION_CONDITIONS = [
  { name: 'Standard_Nominal', category: 'in_distribution' as const, gravity: -10.0, wind: 0.0, turbulence: 0.0 },
  { name: 'Low_Gravity', category: 'in_distribution' as const, gravity: -7.5, wind: 0.0, turbulence: 0.0 },
  { name: 'Heavy_Gravity', category: 'in_distribution' as const, gravity: -12.5, wind: 0.0, turbulence: 0.0 },
  { name: 'Moderate_Wind', category: 'in_distribution' as const, gravity: -10.0, wind: 15.0, turbulence: 1.0 },
  { name: 'Strong_Wind', category: 'in_distribution' as const, gravity: -10.0, wind: 22.0, turbulence: 1.5 },
  { name: 'High_Turbulence', category: 'in_distribution' as const, gravity: -10.0, wind: 12.0, turbulence: 2.5 },
  { name: 'OOD_Extreme_Combined', category: 'out_of_distribution' as const, gravity: -15.0, wind: 30.0, turbulence: 3.5 },
  { name: 'OOD_Microgravity_Shear', category: 'out_of_distribution' as const, gravity: -4.5, wind: 28.0, turbulence: 3.0 },
];

export const PARADIGM_BENCHMARKS: Record<string, ParadigmData> = {
  A_standard: {
    id: 'A_standard',
    name: 'Paradigm A: Standard PPO',
    description: 'Trained exclusively on nominal Box2D physics. Control baseline.',
    training_protocol: 'Single-environment nominal training (500k steps)',
    seeds: [42, 123, 999],
    timesteps_per_run: 500000,
    total_eval_episodes: 2400,
    nominal_outcomes: { success: 164, crash: 127, timeout: 9, out_of_bounds: 0, total: 300 },
    nominal_success_rate: 54.67,
    id_outcomes: { success: 561, crash: 1110, timeout: 53, out_of_bounds: 76, total: 1800 },
    id_success_rate: 31.17,
    ood_outcomes: { success: 12, crash: 388, timeout: 21, out_of_bounds: 179, total: 600 },
    ood_success_rate: 2.0,
    overall_outcomes: { success: 573, crash: 1498, timeout: 74, out_of_bounds: 255, total: 2400 },
    overall_success_rate: 23.88,
    nominal_resting_tilt_deg: 0.75,
    nominal_resting_sample_size: 164,
    terminal_vx: 0.0139,
    terminal_vy: 0.0072,
    main_engine_duty: 45.62,
    side_thruster_duty: 32.23,
    success_rate_ci: {
      mean: 0.3117,
      std: 0.0737,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 0.183,
      lower_bound: 0.1287,
      upper_bound: 0.4947,
    },
    mean_reward_ci: {
      mean: 107.33,
      std: 32.98,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 81.93,
      lower_bound: 25.39,
      upper_bound: 189.26,
    },
    conditions: {
      Standard_Nominal: {
        condition: 'Standard_Nominal',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 164, crash: 127, timeout: 9, out_of_bounds: 0, total: 300 },
        success_rate: 54.67,
        mean_reward: 195.75,
        mean_resting_tilt_deg: 0.75,
        resting_tilt_sample_size: 164,
      },
      Low_Gravity: {
        condition: 'Low_Gravity',
        category: 'in_distribution',
        gravity: -7.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 148, crash: 142, timeout: 10, out_of_bounds: 0, total: 300 },
        success_rate: 49.33,
        mean_reward: 174.22,
      },
      Heavy_Gravity: {
        condition: 'Heavy_Gravity',
        category: 'in_distribution',
        gravity: -12.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 112, crash: 178, timeout: 10, out_of_bounds: 0, total: 300 },
        success_rate: 37.33,
        mean_reward: 121.45,
      },
      Moderate_Wind: {
        condition: 'Moderate_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 15.0,
        turbulence: 1.0,
        outcomes: { success: 72, crash: 211, timeout: 12, out_of_bounds: 5, total: 300 },
        success_rate: 24.0,
        mean_reward: 78.34,
      },
      Strong_Wind: {
        condition: 'Strong_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 22.0,
        turbulence: 1.5,
        outcomes: { success: 38, crash: 228, timeout: 6, out_of_bounds: 28, total: 300 },
        success_rate: 12.67,
        mean_reward: 41.22,
      },
      High_Turbulence: {
        condition: 'High_Turbulence',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 12.0,
        turbulence: 2.5,
        outcomes: { success: 27, crash: 224, timeout: 6, out_of_bounds: 43, total: 300 },
        success_rate: 9.0,
        mean_reward: 32.98,
      },
      OOD_Extreme_Combined: {
        condition: 'OOD_Extreme_Combined',
        category: 'out_of_distribution',
        gravity: -15.0,
        wind: 30.0,
        turbulence: 3.5,
        outcomes: { success: 4, crash: 204, timeout: 11, out_of_bounds: 81, total: 300 },
        success_rate: 1.33,
        mean_reward: -212.45,
      },
      OOD_Microgravity_Shear: {
        condition: 'OOD_Microgravity_Shear',
        category: 'out_of_distribution',
        gravity: -4.5,
        wind: 28.0,
        turbulence: 3.0,
        outcomes: { success: 8, crash: 184, timeout: 10, out_of_bounds: 98, total: 300 },
        success_rate: 2.67,
        mean_reward: -182.44,
      },
    },
  },

  B_dr_only: {
    id: 'B_dr_only',
    name: 'Paradigm B: DR Only (Uncurriculated)',
    description: 'Full domain randomization from step 0. Demonstrates premature variance collapse.',
    training_protocol: 'Direct Domain Randomization without difficulty scaffolding (500k steps)',
    seeds: [42, 123, 999],
    timesteps_per_run: 500000,
    total_eval_episodes: 2400,
    nominal_outcomes: { success: 1, crash: 6, timeout: 292, out_of_bounds: 1, total: 300 },
    nominal_success_rate: 0.33,
    id_outcomes: { success: 22, crash: 325, timeout: 1314, out_of_bounds: 139, total: 1800 },
    id_success_rate: 1.22,
    ood_outcomes: { success: 0, crash: 252, timeout: 88, out_of_bounds: 260, total: 600 },
    ood_success_rate: 0.0,
    overall_outcomes: { success: 22, crash: 577, timeout: 1402, out_of_bounds: 399, total: 2400 },
    overall_success_rate: 0.92,
    nominal_resting_tilt_deg: 0.06,
    nominal_resting_sample_size: 1,
    nominal_resting_caveat: 'Single observation (N=1); cannot support comparative stability claims',
    terminal_vx: 0.0559,
    terminal_vy: 0.0416,
    main_engine_duty: 57.01,
    side_thruster_duty: 33.32,
    success_rate_ci: {
      mean: 0.0122,
      std: 0.0076,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 0.0189,
      lower_bound: -0.0067,
      upper_bound: 0.0311,
    },
    mean_reward_ci: {
      mean: -79.36,
      std: 15.62,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 38.79,
      lower_bound: -118.15,
      upper_bound: -40.57,
    },
    conditions: {
      Standard_Nominal: {
        condition: 'Standard_Nominal',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 1, crash: 6, timeout: 292, out_of_bounds: 1, total: 300 },
        success_rate: 0.33,
        mean_reward: -42.11,
        mean_resting_tilt_deg: 0.06,
        resting_tilt_sample_size: 1,
        resting_tilt_caveat: 'N=1 single observation',
      },
      Low_Gravity: {
        condition: 'Low_Gravity',
        category: 'in_distribution',
        gravity: -7.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 4, crash: 12, timeout: 280, out_of_bounds: 4, total: 300 },
        success_rate: 1.33,
        mean_reward: -68.45,
      },
      Heavy_Gravity: {
        condition: 'Heavy_Gravity',
        category: 'in_distribution',
        gravity: -12.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 2, crash: 48, timeout: 245, out_of_bounds: 5, total: 300 },
        success_rate: 0.67,
        mean_reward: -94.12,
      },
      Moderate_Wind: {
        condition: 'Moderate_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 15.0,
        turbulence: 1.0,
        outcomes: { success: 6, crash: 68, timeout: 202, out_of_bounds: 24, total: 300 },
        success_rate: 2.0,
        mean_reward: -84.22,
      },
      Strong_Wind: {
        condition: 'Strong_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 22.0,
        turbulence: 1.5,
        outcomes: { success: 5, crash: 95, timeout: 152, out_of_bounds: 48, total: 300 },
        success_rate: 1.67,
        mean_reward: -91.55,
      },
      High_Turbulence: {
        condition: 'High_Turbulence',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 12.0,
        turbulence: 2.5,
        outcomes: { success: 4, crash: 96, timeout: 143, out_of_bounds: 57, total: 300 },
        success_rate: 1.33,
        mean_reward: -95.71,
      },
      OOD_Extreme_Combined: {
        condition: 'OOD_Extreme_Combined',
        category: 'out_of_distribution',
        gravity: -15.0,
        wind: 30.0,
        turbulence: 3.5,
        outcomes: { success: 0, crash: 148, timeout: 32, out_of_bounds: 120, total: 300 },
        success_rate: 0.0,
        mean_reward: -248.12,
      },
      OOD_Microgravity_Shear: {
        condition: 'OOD_Microgravity_Shear',
        category: 'out_of_distribution',
        gravity: -4.5,
        wind: 28.0,
        turbulence: 3.0,
        outcomes: { success: 0, crash: 104, timeout: 56, out_of_bounds: 140, total: 300 },
        success_rate: 0.0,
        mean_reward: -207.72,
      },
    },
  },

  C_curriculum_only: {
    id: 'C_curriculum_only',
    name: 'Paradigm C: Curriculum Only',
    description: '4-stage task progression without domain randomization.',
    training_protocol: 'Staged task difficulty in nominal physics (500k steps)',
    seeds: [42, 123, 999],
    timesteps_per_run: 500000,
    total_eval_episodes: 2400,
    nominal_outcomes: { success: 178, crash: 112, timeout: 10, out_of_bounds: 0, total: 300 },
    nominal_success_rate: 59.33,
    id_outcomes: { success: 620, crash: 1043, timeout: 59, out_of_bounds: 78, total: 1800 },
    id_success_rate: 34.44,
    ood_outcomes: { success: 10, crash: 387, timeout: 15, out_of_bounds: 188, total: 600 },
    ood_success_rate: 1.67,
    overall_outcomes: { success: 630, crash: 1430, timeout: 74, out_of_bounds: 266, total: 2400 },
    overall_success_rate: 26.25,
    nominal_resting_tilt_deg: 0.87,
    nominal_resting_sample_size: 178,
    terminal_vx: 0.0094,
    terminal_vy: 0.006,
    main_engine_duty: 47.19,
    side_thruster_duty: 33.88,
    success_rate_ci: {
      mean: 0.3444,
      std: 0.0682,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 0.1694,
      lower_bound: 0.175,
      upper_bound: 0.5138,
    },
    mean_reward_ci: {
      mean: 110.29,
      std: 31.45,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 78.12,
      lower_bound: 32.17,
      upper_bound: 188.41,
    },
    conditions: {
      Standard_Nominal: {
        condition: 'Standard_Nominal',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 178, crash: 112, timeout: 10, out_of_bounds: 0, total: 300 },
        success_rate: 59.33,
        mean_reward: 202.14,
        mean_resting_tilt_deg: 0.87,
        resting_tilt_sample_size: 178,
      },
      Low_Gravity: {
        condition: 'Low_Gravity',
        category: 'in_distribution',
        gravity: -7.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 159, crash: 133, timeout: 8, out_of_bounds: 0, total: 300 },
        success_rate: 53.0,
        mean_reward: 182.55,
      },
      Heavy_Gravity: {
        condition: 'Heavy_Gravity',
        category: 'in_distribution',
        gravity: -12.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 124, crash: 167, timeout: 9, out_of_bounds: 0, total: 300 },
        success_rate: 41.33,
        mean_reward: 134.11,
      },
      Moderate_Wind: {
        condition: 'Moderate_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 15.0,
        turbulence: 1.0,
        outcomes: { success: 84, crash: 198, timeout: 11, out_of_bounds: 7, total: 300 },
        success_rate: 28.0,
        mean_reward: 86.45,
      },
      Strong_Wind: {
        condition: 'Strong_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 22.0,
        turbulence: 1.5,
        outcomes: { success: 44, crash: 218, timeout: 12, out_of_bounds: 26, total: 300 },
        success_rate: 14.67,
        mean_reward: 48.12,
      },
      High_Turbulence: {
        condition: 'High_Turbulence',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 12.0,
        turbulence: 2.5,
        outcomes: { success: 31, crash: 215, timeout: 9, out_of_bounds: 45, total: 300 },
        success_rate: 10.33,
        mean_reward: 37.89,
      },
      OOD_Extreme_Combined: {
        condition: 'OOD_Extreme_Combined',
        category: 'out_of_distribution',
        gravity: -15.0,
        wind: 30.0,
        turbulence: 3.5,
        outcomes: { success: 3, crash: 206, timeout: 8, out_of_bounds: 83, total: 300 },
        success_rate: 1.0,
        mean_reward: -234.12,
      },
      OOD_Microgravity_Shear: {
        condition: 'OOD_Microgravity_Shear',
        category: 'out_of_distribution',
        gravity: -4.5,
        wind: 28.0,
        turbulence: 3.0,
        outcomes: { success: 7, crash: 181, timeout: 7, out_of_bounds: 105, total: 300 },
        success_rate: 2.33,
        mean_reward: -206.68,
      },
    },
  },

  D_curriculum_and_dr: {
    id: 'D_curriculum_and_dr',
    name: 'Paradigm D: Curriculum + DR',
    description: 'Curriculum stages paired with progressive domain randomization envelopes.',
    training_protocol: 'Dual developmental curriculum + domain randomization (500k steps)',
    seeds: [42, 123, 999],
    timesteps_per_run: 500000,
    total_eval_episodes: 2400,
    nominal_outcomes: { success: 186, crash: 110, timeout: 4, out_of_bounds: 0, total: 300 },
    nominal_success_rate: 62.0,
    id_outcomes: { success: 698, crash: 983, timeout: 44, out_of_bounds: 75, total: 1800 },
    id_success_rate: 38.78,
    ood_outcomes: { success: 18, crash: 384, timeout: 18, out_of_bounds: 180, total: 600 },
    ood_success_rate: 3.0,
    overall_outcomes: { success: 716, crash: 1367, timeout: 62, out_of_bounds: 255, total: 2400 },
    overall_success_rate: 29.83,
    nominal_resting_tilt_deg: 0.58,
    nominal_resting_sample_size: 186,
    terminal_vx: 0.0074,
    terminal_vy: 0.005,
    main_engine_duty: 48.31,
    side_thruster_duty: 32.28,
    success_rate_ci: {
      mean: 0.3878,
      std: 0.1941,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 0.4821,
      lower_bound: -0.0943,
      upper_bound: 0.8699,
    },
    mean_reward_ci: {
      mean: 118.09,
      std: 54.12,
      sample_size: 3,
      confidence_level: 0.95,
      margin_of_error: 134.43,
      lower_bound: -16.34,
      upper_bound: 252.52,
    },
    conditions: {
      Standard_Nominal: {
        condition: 'Standard_Nominal',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 186, crash: 110, timeout: 4, out_of_bounds: 0, total: 300 },
        success_rate: 62.0,
        mean_reward: 211.54,
        mean_resting_tilt_deg: 0.58,
        resting_tilt_sample_size: 186,
      },
      Low_Gravity: {
        condition: 'Low_Gravity',
        category: 'in_distribution',
        gravity: -7.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 172, crash: 122, timeout: 6, out_of_bounds: 0, total: 300 },
        success_rate: 57.33,
        mean_reward: 194.88,
      },
      Heavy_Gravity: {
        condition: 'Heavy_Gravity',
        category: 'in_distribution',
        gravity: -12.5,
        wind: 0.0,
        turbulence: 0.0,
        outcomes: { success: 139, crash: 154, timeout: 7, out_of_bounds: 0, total: 300 },
        success_rate: 46.33,
        mean_reward: 149.33,
      },
      Moderate_Wind: {
        condition: 'Moderate_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 15.0,
        turbulence: 1.0,
        outcomes: { success: 104, crash: 181, timeout: 9, out_of_bounds: 6, total: 300 },
        success_rate: 34.67,
        mean_reward: 104.22,
      },
      Strong_Wind: {
        condition: 'Strong_Wind',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 22.0,
        turbulence: 1.5,
        outcomes: { success: 56, crash: 208, timeout: 10, out_of_bounds: 26, total: 300 },
        success_rate: 18.67,
        mean_reward: 62.77,
      },
      High_Turbulence: {
        condition: 'High_Turbulence',
        category: 'in_distribution',
        gravity: -10.0,
        wind: 12.0,
        turbulence: 2.5,
        outcomes: { success: 41, crash: 208, timeout: 8, out_of_bounds: 43, total: 300 },
        success_rate: 13.67,
        mean_reward: 45.76,
      },
      OOD_Extreme_Combined: {
        condition: 'OOD_Extreme_Combined',
        category: 'out_of_distribution',
        gravity: -15.0,
        wind: 30.0,
        turbulence: 3.5,
        outcomes: { success: 6, crash: 207, timeout: 9, out_of_bounds: 78, total: 300 },
        success_rate: 2.0,
        mean_reward: -218.45,
      },
      OOD_Microgravity_Shear: {
        condition: 'OOD_Microgravity_Shear',
        category: 'out_of_distribution',
        gravity: -4.5,
        wind: 28.0,
        turbulence: 3.0,
        outcomes: { success: 12, crash: 177, timeout: 9, out_of_bounds: 102, total: 300 },
        success_rate: 4.0,
        mean_reward: -192.57,
      },
    },
  },
};

export const PAIRWISE_HYPOTHESIS_TESTS: PairwiseTestResult[] = [
  {
    comparison: 'B_dr_only_vs_A_standard',
    pair_label: 'Paradigm B vs. Paradigm A [Reward]',
    t_statistic: -8.2263,
    raw_p_value: 0.0145,
    holm_multiplier: 6,
    holm_alpha: 0.00833,
    holm_adjusted_p_value: 0.0867,
    cohens_d: -4.7495,
    mean_difference: -186.69,
    significant: false,
    verdict: 'Inconclusive under Holm-Bonferroni control (p_adj > 0.05)',
  },
  {
    comparison: 'B_dr_only_vs_A_standard_succ',
    pair_label: 'Paradigm B vs. Paradigm A [Success]',
    t_statistic: -7.5046,
    raw_p_value: 0.0173,
    holm_multiplier: 5,
    holm_alpha: 0.01,
    holm_adjusted_p_value: 0.1038,
    cohens_d: -4.3328,
    mean_difference: -0.2995,
    significant: false,
    verdict: 'Inconclusive under Holm-Bonferroni control (p_adj > 0.05)',
  },
  {
    comparison: 'C_curriculum_only_vs_B_dr_only',
    pair_label: 'Paradigm C vs. Paradigm B [Success]',
    t_statistic: 4.901,
    raw_p_value: 0.0392,
    holm_multiplier: 4,
    holm_alpha: 0.0125,
    holm_adjusted_p_value: 0.196,
    cohens_d: 2.8296,
    mean_difference: 0.3323,
    significant: false,
    verdict: 'Inconclusive under Holm-Bonferroni control (p_adj > 0.05)',
  },
  {
    comparison: 'D_curriculum_and_dr_vs_B_dr_only',
    pair_label: 'Paradigm D vs. Paradigm B [Success]',
    t_statistic: 3.448,
    raw_p_value: 0.0748,
    holm_multiplier: 3,
    holm_alpha: 0.01667,
    holm_adjusted_p_value: 0.2992,
    cohens_d: 1.9907,
    mean_difference: 0.3756,
    significant: false,
    verdict: 'Inconclusive under Holm-Bonferroni control (p_adj > 0.05)',
  },
  {
    comparison: 'D_curriculum_and_dr_vs_A_standard',
    pair_label: 'Paradigm D vs. Paradigm A [Success]',
    t_statistic: 1.0,
    raw_p_value: 0.42265,
    holm_multiplier: 2,
    holm_alpha: 0.025,
    holm_adjusted_p_value: 1.0,
    cohens_d: 0.5774,
    mean_difference: 0.0761,
    significant: false,
    verdict: 'Inconclusive (Large positive effect size d_z = 0.58, but df = 2)',
  },
  {
    comparison: 'D_curriculum_and_dr_vs_C_curriculum_only',
    pair_label: 'Paradigm D vs. Paradigm C [Success]',
    t_statistic: 1.0,
    raw_p_value: 0.42265,
    holm_multiplier: 1,
    holm_alpha: 0.05,
    holm_adjusted_p_value: 1.0,
    cohens_d: 0.5774,
    mean_difference: 0.0433,
    significant: false,
    verdict: 'Inconclusive (Directionally superior, but df = 2)',
  },
];
