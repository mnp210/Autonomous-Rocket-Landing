import React from 'react';
import { PanelContainer } from '../common/PanelContainer';
import { StatusBadge } from '../common/StatusBadge';

interface ParadigmStats {
  id: string;
  name: string;
  totalEpisodes: number;
  nominalSuccess: number;
  nominalSuccessRate: string;
  idMeanSuccessRate: string;
  restingTiltDeg: string;
  tiltSampleSize: string;
  terminalVx: string;
  terminalVy: string;
  mainEngineDuty: string;
  sideEngineDuty: string;
  status: 'nominal' | 'warning' | 'critical' | 'info';
}

const paradigmData: ParadigmStats[] = [
  {
    id: 'D',
    name: 'D: Curriculum + DR',
    totalEpisodes: 300,
    nominalSuccess: 186,
    nominalSuccessRate: '62.0%',
    idMeanSuccessRate: '38.8%',
    restingTiltDeg: '0.58° (0.0101 rad)',
    tiltSampleSize: 'N = 186',
    terminalVx: '0.0074 u/s',
    terminalVy: '0.0050 u/s',
    mainEngineDuty: '48.3%',
    sideEngineDuty: '32.3%',
    status: 'nominal',
  },
  {
    id: 'C',
    name: 'C: Curriculum Only',
    totalEpisodes: 300,
    nominalSuccess: 178,
    nominalSuccessRate: '59.3%',
    idMeanSuccessRate: '34.5%',
    restingTiltDeg: '0.87° (0.0152 rad)',
    tiltSampleSize: 'N = 178',
    terminalVx: '0.0094 u/s',
    terminalVy: '0.0060 u/s',
    mainEngineDuty: '47.2%',
    sideEngineDuty: '33.9%',
    status: 'info',
  },
  {
    id: 'A',
    name: 'A: Standard PPO',
    totalEpisodes: 300,
    nominalSuccess: 164,
    nominalSuccessRate: '54.7%',
    idMeanSuccessRate: '31.2%',
    restingTiltDeg: '0.75° (0.0131 rad)',
    tiltSampleSize: 'N = 164',
    terminalVx: '0.0139 u/s',
    terminalVy: '0.0072 u/s',
    mainEngineDuty: '45.6%',
    sideEngineDuty: '32.2%',
    status: 'muted' as any,
  },
  {
    id: 'B',
    name: 'B: DR Only (Uncurriculated)',
    totalEpisodes: 300,
    nominalSuccess: 1,
    nominalSuccessRate: '0.3%',
    idMeanSuccessRate: '1.2%',
    restingTiltDeg: '0.06° (0.0011 rad)*',
    tiltSampleSize: 'N = 1 (Caveat)*',
    terminalVx: '0.0559 u/s',
    terminalVy: '0.0416 u/s',
    mainEngineDuty: '57.0%',
    sideEngineDuty: '33.3%',
    status: 'critical',
  },
];

const evaluationConditions = [
  { name: 'Standard_Nominal', type: 'In-Distribution', gravity: '-10.0 m/s²', wind: '0.0 m/s', turbulence: '0.0' },
  { name: 'Low_Gravity', type: 'In-Distribution', gravity: '-7.5 m/s²', wind: '0.0 m/s', turbulence: '0.0' },
  { name: 'Heavy_Gravity', type: 'In-Distribution', gravity: '-12.5 m/s²', wind: '0.0 m/s', turbulence: '0.0' },
  { name: 'Moderate_Wind', type: 'In-Distribution', gravity: '-10.0 m/s²', wind: '15.0 m/s', turbulence: '1.0' },
  { name: 'Strong_Wind', type: 'In-Distribution', gravity: '-10.0 m/s²', wind: '22.0 m/s', turbulence: '1.5' },
  { name: 'High_Turbulence', type: 'In-Distribution', gravity: '-10.0 m/s²', wind: '12.0 m/s', turbulence: '2.5' },
  { name: 'OOD_Extreme_Combined', type: 'Out-Of-Distribution', gravity: '-15.0 m/s²', wind: '30.0 m/s', turbulence: '3.5' },
  { name: 'OOD_Microgravity_Shear', type: 'Out-Of-Distribution', gravity: '-4.5 m/s²', wind: '28.0 m/s', turbulence: '3.0' },
];

export const BenchmarkMatrix: React.FC = () => {
  return (
    <div className="space-y-4 font-mono text-xs">
      {/* 1. Paradigm Comparison Table */}
      <PanelContainer
        title="EMPIRICAL BENCHMARK MATRIX (12 RUNS, 9,600 EVALUATION EPISODES)"
        subtitle="Forensic Reconciled Audit Data from docs/benchmark_results.md"
        badge={<StatusBadge label="VERIFIED ARTIFACTS" variant="nominal" size="sm" />}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#101622] text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <th className="py-2 px-3">Paradigm</th>
                <th className="py-2 px-3 text-right">Nominal Success</th>
                <th className="py-2 px-3 text-right">ID Mean Success</th>
                <th className="py-2 px-3 text-right">Resting Tilt (Deg)</th>
                <th className="py-2 px-3 text-right">Tilt Sample (N)</th>
                <th className="py-2 px-3 text-right">Terminal |Vx|</th>
                <th className="py-2 px-3 text-right">Terminal |Vy|</th>
                <th className="py-2 px-3 text-right">Main Throttle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 tabular-nums">
              {paradigmData.map((row) => (
                <tr
                  key={row.id}
                  className={`hover:bg-[#141B26] transition-colors ${
                    row.id === 'D' ? 'bg-cyan-950/20 font-bold' : ''
                  }`}
                >
                  <td className="py-2.5 px-3 flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        row.status === 'nominal'
                          ? 'bg-emerald-400'
                          : row.status === 'critical'
                          ? 'bg-rose-400'
                          : row.status === 'info'
                          ? 'bg-cyan-400'
                          : 'bg-slate-400'
                      }`}
                    />
                    <span className="text-slate-100">{row.name}</span>
                  </td>
                  <td
                    className={`py-2.5 px-3 text-right font-bold ${
                      row.id === 'D' ? 'text-emerald-400' : 'text-slate-200'
                    }`}
                  >
                    {row.nominalSuccessRate}
                  </td>
                  <td
                    className={`py-2.5 px-3 text-right font-bold ${
                      row.id === 'D' ? 'text-cyan-400' : 'text-slate-200'
                    }`}
                  >
                    {row.idMeanSuccessRate}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-300">
                    {row.restingTiltDeg}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-400 text-[11px]">
                    {row.tiltSampleSize}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-300">{row.terminalVx}</td>
                  <td className="py-2.5 px-3 text-right text-slate-300">{row.terminalVy}</td>
                  <td className="py-2.5 px-3 text-right text-slate-300">{row.mainEngineDuty}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Scientific sample size warning */}
        <div className="mt-3 p-2.5 rounded bg-[#101622] border border-amber-500/30 text-[11px] text-slate-300 space-y-1">
          <div className="flex items-center gap-1.5 text-amber-400 font-bold text-[10px] uppercase">
            <span>⚠️ FORENSIC RESEARCH RECONCILIATION NOTICE:</span>
          </div>
          <p className="text-slate-400 text-[10px] leading-relaxed">
            * <strong>Paradigm B Sample Size Caveat:</strong> Paradigm B (Domain Randomization without curriculum) achieved only a single successful landing out of 300 nominal flights (0.3%). Its resting tilt (0.06°) is an isolated single-observation outlier ($N=1$) and must not be cited as superior stability.
          </p>
          <p className="text-slate-400 text-[10px] leading-relaxed">
            * <strong>Kinematics Denominator:</strong> In Box2D LunarLander, genuine landings come to complete rest ($v_x=0, v_y=0$). The non-zero terminal velocities reported above represent the kinetic energy of failed attempts and crashes at terminal step across all 300 episodes.
          </p>
        </div>
      </PanelContainer>

      {/* 2. Evaluated Environmental Conditions Matrix */}
      <PanelContainer
        title="DISTRIBUTIONAL EVALUATION SUITE (8 TEST CONDITIONS)"
        subtitle="100 Evaluation Episodes per Condition per Seed per Model"
        badge={<StatusBadge label="6 ID // 2 OOD" variant="info" size="sm" />}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
          {evaluationConditions.map((cond, idx) => (
            <div
              key={idx}
              className="p-2.5 rounded bg-[#101622] border border-slate-800/80 flex flex-col justify-between"
            >
              <div className="flex items-center justify-between text-[10px] mb-1">
                <span className="font-bold text-slate-200">{cond.name}</span>
                <span
                  className={`text-[9px] px-1 rounded font-semibold ${
                    cond.type === 'In-Distribution'
                      ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                      : 'bg-purple-950 text-purple-300 border border-purple-800'
                  }`}
                >
                  {cond.type === 'In-Distribution' ? 'ID' : 'OOD'}
                </span>
              </div>
              <div className="text-[10px] text-slate-400 space-y-0.5 tabular-nums">
                <div className="flex justify-between">
                  <span>Gravity:</span>
                  <span className="text-slate-200">{cond.gravity}</span>
                </div>
                <div className="flex justify-between">
                  <span>Wind:</span>
                  <span className="text-slate-200">{cond.wind}</span>
                </div>
                <div className="flex justify-between">
                  <span>Turbulence:</span>
                  <span className="text-slate-200">{cond.turbulence}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </PanelContainer>

      {/* 3. Statistical Rigor & Scientific Integrity Verdict */}
      <PanelContainer
        title="STATISTICAL RIGOR & CLAIM VERDICT"
        subtitle="Independent Hypothesis Testing (df=2, N=3 Seeds)"
        badge={<StatusBadge label="EXPLORATORY EVIDENCE" variant="warning" size="sm" />}
      >
        <div className="p-3 rounded bg-[#090D14] border border-slate-800 space-y-2 text-[11px] leading-relaxed text-slate-300">
          <p>
            Under formal <strong className="text-cyan-400">Holm-Bonferroni correction</strong> across the family of 6 pairwise comparisons ($m=6$), no paradigm comparison achieves formal statistical significance at $\alpha = 0.05$ due to between-seed variance across $N=3$ training seeds.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            <div className="p-2 rounded bg-[#101622] border border-emerald-500/30 text-[10px]">
              <span className="text-emerald-400 font-bold block mb-1">✓ SCIENTIFICALLY VALID FINDING:</span>
              <span>Combining Curriculum Learning with Domain Randomization achieved directional superiority across all 6 In-Distribution conditions (38.8% vs 31.2% baseline; 62.0% nominal vs 54.7% baseline) with large positive effect sizes ($d_z \approx 0.58$).</span>
            </div>
            <div className="p-2 rounded bg-[#101622] border border-rose-500/30 text-[10px]">
              <span className="text-rose-400 font-bold block mb-1">✗ REJECTED CLAIM:</span>
              <span>"Curriculum learning has been proven statistically significant ($p &lt; 0.05$)." Such claims fail formal family-wise error rate control on $N=3$ seeds. Results constitute robust exploratory empirical evidence.</span>
            </div>
          </div>
        </div>
      </PanelContainer>
    </div>
  );
};
