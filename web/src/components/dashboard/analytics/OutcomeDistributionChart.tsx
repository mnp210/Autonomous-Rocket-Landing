import React, { useState } from 'react';
import { PanelContainer } from '../../common/PanelContainer';
import { StatusBadge } from '../../common/StatusBadge';
import {
  PARADIGM_BENCHMARKS,
  type OutcomeCounts,
} from '../../../data/benchmarkData';

type FilterScope = 'nominal' | 'in_distribution' | 'out_of_distribution' | 'overall';

export const OutcomeDistributionChart: React.FC = () => {
  const [scope, setScope] = useState<FilterScope>('nominal');

  const getOutcomes = (paradigmId: string): OutcomeCounts => {
    const data = PARADIGM_BENCHMARKS[paradigmId];
    if (scope === 'nominal') return data.nominal_outcomes;
    if (scope === 'in_distribution') return data.id_outcomes;
    if (scope === 'out_of_distribution') return data.ood_outcomes;
    return data.overall_outcomes;
  };

  const getSuccessRate = (paradigmId: string): number => {
    const data = PARADIGM_BENCHMARKS[paradigmId];
    if (scope === 'nominal') return data.nominal_success_rate;
    if (scope === 'in_distribution') return data.id_success_rate;
    if (scope === 'out_of_distribution') return data.ood_success_rate;
    return data.overall_success_rate;
  };

  const paradigms = [
    { id: 'D_curriculum_and_dr', label: 'D: Curriculum + DR' },
    { id: 'C_curriculum_only', label: 'C: Curriculum Only' },
    { id: 'A_standard', label: 'A: Standard Baseline' },
    { id: 'B_dr_only', label: 'B: DR Only (Uncurriculated)' },
  ];

  return (
    <PanelContainer
      title="EPISODE OUTCOME DISTRIBUTIONS (N = 9,600 EVALUATIONS)"
      subtitle="Exhaustive Breakdown: Success, Crash, Timeout, and Out-of-Bounds Rates"
      badge={
        <StatusBadge
          label={scope.toUpperCase().replace('_', ' ')}
          variant="info"
          size="sm"
        />
      }
      actionSlot={
        <div className="flex items-center gap-1 bg-[#090D14] p-0.5 rounded border border-slate-800 text-[10px]">
          <button
            type="button"
            onClick={() => setScope('nominal')}
            className={`px-2 py-0.5 rounded font-bold transition-all ${
              scope === 'nominal'
                ? 'bg-cyan-950 border border-cyan-400 text-cyan-300'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            NOMINAL (N=300)
          </button>
          <button
            type="button"
            onClick={() => setScope('in_distribution')}
            className={`px-2 py-0.5 rounded font-bold transition-all ${
              scope === 'in_distribution'
                ? 'bg-cyan-950 border border-cyan-400 text-cyan-300'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            IN-DIST (N=1800)
          </button>
          <button
            type="button"
            onClick={() => setScope('out_of_distribution')}
            className={`px-2 py-0.5 rounded font-bold transition-all ${
              scope === 'out_of_distribution'
                ? 'bg-cyan-950 border border-cyan-400 text-cyan-300'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            OOD (N=600)
          </button>
          <button
            type="button"
            onClick={() => setScope('overall')}
            className={`px-2 py-0.5 rounded font-bold transition-all ${
              scope === 'overall'
                ? 'bg-cyan-950 border border-cyan-400 text-cyan-300'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            ALL (N=2400)
          </button>
        </div>
      }
    >
      <div className="space-y-3 font-mono text-xs">
        {/* Legend */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-[#090D14] border border-slate-800 text-[10px]">
          <span className="text-slate-400 uppercase font-semibold">OUTCOME CATEGORIES:</span>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-2.5 h-2.5 rounded-xs bg-emerald-500" />
              SUCCESS (TOUCHDOWN)
            </span>
            <span className="flex items-center gap-1.5 text-rose-400">
              <span className="w-2.5 h-2.5 rounded-xs bg-rose-500" />
              CRASH (COLLISION)
            </span>
            <span className="flex items-center gap-1.5 text-amber-400">
              <span className="w-2.5 h-2.5 rounded-xs bg-amber-500" />
              TIMEOUT (HORIZON)
            </span>
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-2.5 h-2.5 rounded-xs bg-slate-600" />
              OUT OF BOUNDS
            </span>
          </div>
        </div>

        {/* Stacked Outcome Bars */}
        <div className="space-y-2.5">
          {paradigms.map((p) => {
            const counts = getOutcomes(p.id);
            const succPct = (counts.success / counts.total) * 100;
            const crashPct = (counts.crash / counts.total) * 100;
            const timeoutPct = (counts.timeout / counts.total) * 100;
            const oobPct = (counts.out_of_bounds / counts.total) * 100;
            const rate = getSuccessRate(p.id);

            return (
              <div
                key={p.id}
                className="p-2.5 rounded bg-[#101622] border border-slate-800/80 flex flex-col gap-1.5"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-bold text-slate-100">{p.label}</span>
                  <div className="flex items-center gap-3 tabular-nums">
                    <span className="text-slate-400 text-[10px]">
                      TOTAL: {counts.total} EPISODES
                    </span>
                    <span
                      className={`font-bold ${
                        rate > 50
                          ? 'text-emerald-400'
                          : rate > 25
                          ? 'text-cyan-300'
                          : rate > 5
                          ? 'text-amber-400'
                          : 'text-rose-400'
                      }`}
                    >
                      SUCCESS: {rate.toFixed(1)}% ({counts.success})
                    </span>
                  </div>
                </div>

                {/* Stacked Horizontal Bar */}
                <div className="w-full h-4 rounded overflow-hidden flex bg-slate-900 border border-slate-800">
                  {succPct > 0 && (
                    <div
                      title={`Success: ${counts.success} (${succPct.toFixed(1)}%)`}
                      style={{ width: `${succPct}%` }}
                      className="bg-emerald-500 h-full transition-all"
                    />
                  )}
                  {crashPct > 0 && (
                    <div
                      title={`Crash: ${counts.crash} (${crashPct.toFixed(1)}%)`}
                      style={{ width: `${crashPct}%` }}
                      className="bg-rose-500 h-full transition-all"
                    />
                  )}
                  {timeoutPct > 0 && (
                    <div
                      title={`Timeout: ${counts.timeout} (${timeoutPct.toFixed(1)}%)`}
                      style={{ width: `${timeoutPct}%` }}
                      className="bg-amber-500 h-full transition-all"
                    />
                  )}
                  {oobPct > 0 && (
                    <div
                      title={`Out of Bounds: ${counts.out_of_bounds} (${oobPct.toFixed(1)}%)`}
                      style={{ width: `${oobPct}%` }}
                      className="bg-slate-600 h-full transition-all"
                    />
                  )}
                </div>

                {/* Numeric Breakdown */}
                <div className="flex justify-between text-[10px] text-slate-400 tabular-nums pt-0.5">
                  <span className="text-emerald-400">
                    Success: {counts.success} ({succPct.toFixed(1)}%)
                  </span>
                  <span className="text-rose-400">
                    Crash: {counts.crash} ({crashPct.toFixed(1)}%)
                  </span>
                  <span className="text-amber-400">
                    Timeout: {counts.timeout} ({timeoutPct.toFixed(1)}%)
                  </span>
                  <span className="text-slate-400">
                    OOB: {counts.out_of_bounds} ({oobPct.toFixed(1)}%)
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Scientific Context Callout */}
        <div className="p-2 rounded bg-[#090D14] border border-cyan-500/30 text-[10px] text-slate-400">
          <strong className="text-cyan-400 uppercase">MATHEMATICAL CONSERVATION:</strong> Rates sum to strictly 100.0% across all {getOutcomes('A_standard').total} completed evaluation rollouts per paradigm. Incomplete episodes are never counted as successes.
        </div>
      </div>
    </PanelContainer>
  );
};
