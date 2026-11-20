import React from 'react';
import { PanelContainer } from '../../common/PanelContainer';
import { StatusBadge } from '../../common/StatusBadge';
import {
  EVALUATION_CONDITIONS,
  PARADIGM_BENCHMARKS,
} from '../../../data/benchmarkData';

export const EnvironmentalRobustnessView: React.FC = () => {
  return (
    <PanelContainer
      title="DISTRIBUTIONAL ROBUSTNESS EVALUATION (8 STRESS ENVIRONMENTS)"
      subtitle="100 Rollouts per Condition per Seed (2,400 Total Episodes per Paradigm)"
      badge={<StatusBadge label="6 ID // 2 OOD" variant="info" size="sm" />}
    >
      <div className="space-y-3 font-mono text-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#101622] text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <th className="py-2.5 px-3">Condition & Stress Envelope</th>
                <th className="py-2.5 px-3 text-center">Category</th>
                <th className="py-2.5 px-3 text-right">D: Curr + DR</th>
                <th className="py-2.5 px-3 text-right">C: Curr Only</th>
                <th className="py-2.5 px-3 text-right">A: Standard</th>
                <th className="py-2.5 px-3 text-right">B: DR Only</th>
                <th className="py-2.5 px-3 text-center">Robustness Delta (D vs A)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 tabular-nums">
              {EVALUATION_CONDITIONS.map((cond) => {
                const pD = PARADIGM_BENCHMARKS.D_curriculum_and_dr.conditions[cond.name];
                const pC = PARADIGM_BENCHMARKS.C_curriculum_only.conditions[cond.name];
                const pA = PARADIGM_BENCHMARKS.A_standard.conditions[cond.name];
                const pB = PARADIGM_BENCHMARKS.B_dr_only.conditions[cond.name];

                const delta = pD.success_rate - pA.success_rate;

                return (
                  <tr key={cond.name} className="hover:bg-[#141B26] transition-colors">
                    <td className="py-2.5 px-3">
                      <div className="font-bold text-slate-200">{cond.name}</div>
                      <div className="text-[10px] text-slate-500">
                        g: {cond.gravity} m/s² | Wind: {cond.wind} m/s | Turb: {cond.turbulence}
                      </div>
                    </td>

                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                          cond.category === 'in_distribution'
                            ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                            : 'bg-purple-950 text-purple-300 border border-purple-800'
                        }`}
                      >
                        {cond.category === 'in_distribution' ? 'IN-DIST' : 'OUT-OF-DIST'}
                      </span>
                    </td>

                    <td className="py-2.5 px-3 text-right font-bold text-emerald-400">
                      {pD.success_rate.toFixed(1)}%
                    </td>

                    <td className="py-2.5 px-3 text-right font-semibold text-cyan-300">
                      {pC.success_rate.toFixed(1)}%
                    </td>

                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {pA.success_rate.toFixed(1)}%
                    </td>

                    <td className="py-2.5 px-3 text-right text-rose-400">
                      {pB.success_rate.toFixed(1)}%
                    </td>

                    <td className="py-2.5 px-3 text-center font-bold">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          delta > 0
                            ? 'text-emerald-400 bg-emerald-950/60 border border-emerald-500/30'
                            : delta < 0
                            ? 'text-rose-400 bg-rose-950/60 border border-rose-500/30'
                            : 'text-slate-400'
                        }`}
                      >
                        {delta > 0 ? `+${delta.toFixed(1)}%` : `${delta.toFixed(1)}%`}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Analytical takeaways */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1 text-[11px] leading-relaxed">
          <div className="p-2.5 rounded bg-[#090D14] border border-cyan-500/30 text-slate-300">
            <span className="text-cyan-400 font-bold block mb-1 uppercase">
              1. Crosswind Generalization:
            </span>
            <span>
              Under Strong Wind (22 m/s), Standard PPO (Paradigm A) drops from 54.7% down to 12.7% (zero-shot failure). Paradigm D maintains 18.7% success due to domain randomization conditioning during curriculum stages.
            </span>
          </div>

          <div className="p-2.5 rounded bg-[#090D14] border border-purple-500/30 text-slate-300">
            <span className="text-purple-400 font-bold block mb-1 uppercase">
              2. Out-of-Distribution Degradation:
            </span>
            <span>
              In OOD Extreme Combined (g=-15, wind=30, turb=3.5), all paradigms degrade to &lt; 3% success rate, confirming that parameters exceeding the maximum training envelope produce physical control saturation regardless of training strategy.
            </span>
          </div>
        </div>
      </div>
    </PanelContainer>
  );
};
