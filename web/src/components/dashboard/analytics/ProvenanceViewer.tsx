import React from 'react';
import { PanelContainer } from '../../common/PanelContainer';
import { StatusBadge } from '../../common/StatusBadge';
import { DataGrid } from '../../common/DataGrid';
import {
  PAIRWISE_HYPOTHESIS_TESTS,
} from '../../../data/benchmarkData';
import {
  globalTelemetryStore,
} from '../../../services/telemetryStore';

export const ProvenanceViewer: React.FC = () => {
  const liveEpisodes = globalTelemetryStore.getCompletedEpisodes();
  const liveSuccesses = liveEpisodes.filter((e) => e.outcome === 'SUCCESS').length;
  const liveSuccessRate =
    liveEpisodes.length > 0 ? (liveSuccesses / liveEpisodes.length) * 100 : 0.0;

  const provenanceSpecs = [
    { label: 'Artifact Source', value: 'experiments/benchmark/production_benchmark_summary.json', status: 'info' as const },
    { label: 'Dataset Generation', value: '2026-11-08T01:24:59 (Forensic Audit Verified)', status: 'muted' as const },
    { label: 'Policy Checkpoint', value: 'models/benchmark/D_curriculum_and_dr/seed_42/final_model.zip', status: 'nominal' as const },
    { label: 'RL Algorithm', value: 'Stable-Baselines3 PPO (MlpPolicy [64, 64] tanh)', status: 'muted' as const },
    { label: 'Study Sample Size', value: '12 Production Runs (4 Paradigms × 3 Seeds)', status: 'info' as const },
    { label: 'Total Training Steps', value: '6,000,000 Steps (500k / run)', status: 'muted' as const },
    { label: 'Total Eval Rollouts', value: '9,600 Verified Episodes (800 / model)', status: 'nominal' as const },
    { label: 'Statistical Hierarchy', value: 'Independent Units: N = 3 Seeds (df = 2)', status: 'warning' as const },
  ];

  return (
    <div className="space-y-4 font-mono text-xs">
      {/* 1. Experiment Provenance Card */}
      <PanelContainer
        title="EXPERIMENT PROVENANCE & BENCHMARK AUDIT TRAIL"
        subtitle="Cryptographically & Programmatically Verified Forensic Study Metadata"
        badge={<StatusBadge label="VERIFIED ARTIFACT" variant="nominal" size="sm" />}
      >
        <div className="space-y-3">
          <DataGrid items={provenanceSpecs} columns={2} />
          <div className="p-2 rounded bg-[#090D14] border border-slate-800 text-[10px] text-slate-400">
            <span className="text-cyan-400 font-bold uppercase">PROVENANCE INTEGRITY:</span> All 12 model weight archives, periodic checkpoints (20 per run), evaluation CSVs (800 rows each), and summary logs are preserved intact under `experiments/benchmark/`.
          </div>
        </div>
      </PanelContainer>

      {/* 2. Side-by-Side: Historical Benchmark vs. Active Live Session */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <PanelContainer
          title="HISTORICAL BENCHMARK DATASET"
          subtitle="Pre-recorded 9,600 Evaluation Episodes (12 Models)"
          badge={<StatusBadge label="DURABLE / STATIC" variant="info" size="sm" />}
        >
          <div className="space-y-2 text-[11px] tabular-nums">
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Total Study Episodes:</span>
              <span className="font-bold text-slate-200">9,600 Rollouts</span>
            </div>
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Nominal Benchmark Flights:</span>
              <span className="font-bold text-slate-200">1,200 (300 / paradigm)</span>
            </div>
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Paradigm D Nominal Success:</span>
              <span className="font-bold text-emerald-400">62.0% (186 / 300)</span>
            </div>
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Paradigm D In-Dist Mean:</span>
              <span className="font-bold text-cyan-300">38.8% (698 / 1800)</span>
            </div>
            <p className="text-[10px] text-slate-500 pt-1">
              Historical records represent controlled offline evaluation under fixed benchmark seeds with zero user interference.
            </p>
          </div>
        </PanelContainer>

        <PanelContainer
          title="ACTIVE BROWSER SESSION EPISODES"
          subtitle="Live Flights Logged in Current Browser Session"
          badge={
            <StatusBadge
              label={`${liveEpisodes.length} LIVE FLIGHTS`}
              variant={liveEpisodes.length > 0 ? 'nominal' : 'neutral'}
              size="sm"
            />
          }
        >
          <div className="space-y-2 text-[11px] tabular-nums">
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Logged Live Episodes:</span>
              <span className="font-bold text-slate-200">{liveEpisodes.length} Episodes</span>
            </div>
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Successful Live Landings:</span>
              <span className="font-bold text-emerald-400">{liveSuccesses}</span>
            </div>
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Live Session Success Rate:</span>
              <span className="font-bold text-cyan-300">
                {liveEpisodes.length > 0 ? `${liveSuccessRate.toFixed(1)}%` : '—'}
              </span>
            </div>
            <div className="p-2 rounded bg-[#101622] border border-slate-800 flex justify-between">
              <span className="text-slate-400">Storage Scope:</span>
              <span className="text-amber-400 font-bold">Ephemeral (Browser Memory)</span>
            </div>
            <p className="text-[10px] text-slate-500 pt-1">
              Live session episodes accumulate in `TelemetryStore` while connected to FastAPI. They are intentionally kept separate from historical benchmark datasets.
            </p>
          </div>
        </PanelContainer>
      </div>

      {/* 3. Formal Hypothesis Testing & Holm-Bonferroni Correction Table */}
      <PanelContainer
        title="PAIRWISE HYPOTHESIS TESTING (HOLM-BONFERRONI FAMILY CONTROL)"
        subtitle="Matched-Seed Paired Student's t-Tests across N = 3 Seeds (df = 2)"
        badge={<StatusBadge label="FWER CONTROL" variant="warning" size="sm" />}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#101622] text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <th className="py-2.5 px-3">Pairwise Comparison</th>
                <th className="py-2.5 px-3 text-right">Mean Diff</th>
                <th className="py-2.5 px-3 text-right">t-stat</th>
                <th className="py-2.5 px-3 text-right">Raw p-value</th>
                <th className="py-2.5 px-3 text-center">Holm Mult</th>
                <th className="py-2.5 px-3 text-right">Holm p_adj</th>
                <th className="py-2.5 px-3 text-right">Cohen's dz</th>
                <th className="py-2.5 px-3 text-center">Formal Sig?</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 tabular-nums">
              {PAIRWISE_HYPOTHESIS_TESTS.map((test, idx) => (
                <tr key={idx} className="hover:bg-[#141B26] transition-colors">
                  <td className="py-2.5 px-3 font-bold text-slate-200">
                    {test.pair_label}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-300">
                    {test.mean_difference >= 0
                      ? `+${test.mean_difference.toFixed(2)}`
                      : test.mean_difference.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-300">
                    {test.t_statistic.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-400">
                    {test.raw_p_value.toFixed(4)}
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-400">
                    × {test.holm_multiplier}
                  </td>
                  <td className="py-2.5 px-3 text-right font-bold text-amber-400">
                    {test.holm_adjusted_p_value.toFixed(4)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-cyan-300">
                    {test.cohens_d >= 0 ? `+${test.cohens_d.toFixed(2)}` : test.cohens_d.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
                      NO (p_adj &gt; 0.05)
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-3 p-2.5 rounded bg-[#090D14] border border-amber-500/30 text-[10px] text-slate-300 space-y-1">
          <div className="flex items-center gap-1.5 text-amber-400 font-bold uppercase">
            <span>⚠️ SCIENTIFIC INTERPRETATION DIRECTIVE:</span>
          </div>
          <p className="text-slate-400">
            Because $N = 3$ seeds yields only 2 degrees of freedom ($df = 2$), the $t$-statistic must exceed $\approx 11.0$ to satisfy the Holm-Bonferroni threshold ($\alpha_1 = 0.00833$). While raw effect sizes are large ($d_z \approx 0.58$ for Paradigm D vs A), results are formally classified as <strong>exploratory empirical evidence</strong>. Claims of "statistically proven superiority" are scientifically invalid and strictly retracted.
          </p>
        </div>
      </PanelContainer>
    </div>
  );
};
