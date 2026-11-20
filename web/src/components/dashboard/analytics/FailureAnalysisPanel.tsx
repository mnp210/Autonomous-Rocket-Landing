import React from 'react';
import { PanelContainer } from '../../common/PanelContainer';
import { StatusBadge } from '../../common/StatusBadge';
import { PARADIGM_BENCHMARKS } from '../../../data/benchmarkData';

export const FailureAnalysisPanel: React.FC = () => {
  const failureTaxonomy = [
    {
      category: 'KINETIC COLLISION (HIGH SINK RATE)',
      mechanism: 'Excessive descent velocity (|vy| > 0.40 u/s) upon pad contact resulting in structural collapse (-100 reward).',
      prevalence: 'Dominant failure mode in Standard Baseline (Paradigm A) under high gravity and sudden down-drafts.',
      severity: 'Catastrophic',
      badgeColor: 'critical' as const,
    },
    {
      category: 'AERODYNAMIC ROLLOVER / TUMBLE',
      mechanism: 'Pitch angle (|θ| > 0.20 rad) or angular rate (|dθ/dt| > 0.35 rad/s) exceeded during landing, tripping the footpad.',
      prevalence: 'Primary failure mode under Moderate Wind (15 m/s) and High Turbulence (2.5) for uncurriculated policies.',
      severity: 'Critical',
      badgeColor: 'warning' as const,
    },
    {
      category: 'HORIZON CUTOFF / TIMEOUT (>1000 STEPS)',
      mechanism: 'Vehicle hovers or drifts in upper atmosphere without committing to a terminal descent corridor.',
      prevalence: 'Accounts for 97.3% of Paradigm B (DR Only) failures. The policy learned perpetual hover to avoid crash penalties.',
      severity: 'Non-Convergent',
      badgeColor: 'warning' as const,
    },
    {
      category: 'LATERAL DISPLACEMENT / HELIPAD MISS',
      mechanism: 'Lander touches down outside helipad target boundaries (|x| > 0.25 u) or drifts off screen.',
      prevalence: 'Occurs primarily in Out-of-Distribution shear wind (28-30 m/s) exceeding control authority envelope.',
      severity: 'Mission Failure',
      badgeColor: 'neutral' as const,
    },
  ];

  return (
    <div className="space-y-4 font-mono text-xs">
      {/* 1. Failure Taxonomy Matrix */}
      <PanelContainer
        title="EMPIRICAL FAILURE TAXONOMY & MECHANICAL ROOT CAUSES"
        subtitle="Forensic Analysis of 7,659 Failed Evaluation Rollouts across 4 Paradigms"
        badge={<StatusBadge label="VERIFIED CRASH REASONS" variant="critical" size="sm" />}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {failureTaxonomy.map((item, idx) => (
            <div
              key={idx}
              className="p-3 rounded bg-[#101622] border border-slate-800/80 flex flex-col justify-between gap-2"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="font-bold text-slate-100 text-[11px] uppercase">
                    {item.category}
                  </span>
                  <StatusBadge label={item.severity} variant={item.badgeColor} size="sm" />
                </div>
                <p className="text-[10px] text-slate-300 leading-relaxed font-normal">
                  {item.mechanism}
                </p>
              </div>

              <div className="p-1.5 rounded bg-[#090D14] border border-slate-800 text-[9px] text-slate-400">
                <span className="text-cyan-400 font-bold uppercase">OBSERVED DYNAMICS:</span>{' '}
                {item.prevalence}
              </div>
            </div>
          ))}
        </div>
      </PanelContainer>

      {/* 2. Deep Dive: Why Paradigm B Collapsed */}
      <PanelContainer
        title="CASE STUDY: THE PARADIGM B 'PERPETUAL HOVER' COLLAPSE"
        subtitle="Forensic Explanation of 97.3% Timeout Rate in Raw Domain Randomization"
        badge={<StatusBadge label="RL FAILURE MODE" variant="warning" size="sm" />}
      >
        <div className="p-3 rounded bg-[#090D14] border border-amber-500/30 space-y-2 text-[11px] text-slate-300 leading-relaxed">
          <p>
            When training <strong>Paradigm B (Domain Randomization Only)</strong>, the agent was exposed to wide gravity variations (-13 to -7 m/s²) and violent crosswinds (25 m/s) from step 0 with zero developmental scaffolding.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 py-1 tabular-nums">
            <div className="p-2 rounded bg-[#101622] border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 block uppercase">TOTAL TIMEOUTS</span>
              <span className="text-lg font-bold text-amber-400">
                {PARADIGM_BENCHMARKS.B_dr_only.nominal_outcomes.timeout} / 300
              </span>
              <span className="text-[9px] text-slate-500 block">97.3% in Nominal Physics</span>
            </div>

            <div className="p-2 rounded bg-[#101622] border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 block uppercase">SUCCESSFUL LANDINGS</span>
              <span className="text-lg font-bold text-rose-400">
                {PARADIGM_BENCHMARKS.B_dr_only.nominal_outcomes.success} / 300
              </span>
              <span className="text-[9px] text-slate-500 block">0.3% Nominal Success</span>
            </div>

            <div className="p-2 rounded bg-[#101622] border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 block uppercase">SAMPLE SIZE CAVEAT</span>
              <span className="text-lg font-bold text-cyan-300">N = 1</span>
              <span className="text-[9px] text-slate-500 block">Single Observation Tilt</span>
            </div>
          </div>
          <p className="text-[10px] text-slate-400">
            <strong>Theoretical Takeaway:</strong> Without curriculum stages (e.g. initial hover $\to$ gentle descent $\to$ disturbance rejection), the PPO actor discovered a local optimum: maintaining high throttle to float until step 1000 avoids the $-100$ collision penalty, completely aborting terminal descent.
          </p>
        </div>
      </PanelContainer>
    </div>
  );
};
