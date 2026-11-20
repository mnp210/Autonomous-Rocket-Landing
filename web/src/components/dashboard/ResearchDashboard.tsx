import React, { useState } from 'react';
import { TabNavigation } from '../common/TabNavigation';
import { BenchmarkMatrix } from './BenchmarkMatrix';
import { ExperimentContextCard } from './ExperimentContextCard';
import { AnalyticsShell } from './AnalyticsShell';
import { OutcomeDistributionChart } from './analytics/OutcomeDistributionChart';
import { FailureAnalysisPanel } from './analytics/FailureAnalysisPanel';
import { EnvironmentalRobustnessView } from './analytics/EnvironmentalRobustnessView';
import { ProvenanceViewer } from './analytics/ProvenanceViewer';

export type ResearchSubTab =
  | 'benchmarks'
  | 'outcomes'
  | 'robustness'
  | 'provenance'
  | 'analytics'
  | 'specs';

export interface ResearchDashboardProps {
  activeSubTab?: ResearchSubTab;
  onSubTabChange?: (tab: ResearchSubTab) => void;
}

export const ResearchDashboard: React.FC<ResearchDashboardProps> = ({
  activeSubTab: controlledSubTab,
  onSubTabChange,
}) => {
  const [internalSubTab, setInternalSubTab] = useState<ResearchSubTab>('benchmarks');
  const activeSubTab = controlledSubTab ?? internalSubTab;
  const setActiveSubTab = (tab: ResearchSubTab) => {
    if (onSubTabChange) {
      onSubTabChange(tab);
    } else {
      setInternalSubTab(tab);
    }
  };

  const tabs = [
    { id: 'benchmarks', label: 'PARADIGM MATRIX', badge: '12 RUNS' },
    { id: 'outcomes', label: 'OUTCOMES & FAILURES', badge: '9,600 EPS' },
    { id: 'robustness', label: 'ENVIRONMENTAL STRESS', badge: '8 CONDS' },
    { id: 'provenance', label: 'PROVENANCE & STATS', badge: 'df=2' },
    { id: 'analytics', label: 'FLIGHT DYNAMICS', badge: '4 CHARTS' },
    { id: 'specs', label: 'SYSTEM SPECS', badge: 'PPO' },
  ];

  return (
    <div className="flex-1 flex flex-col gap-3 max-w-[1920px] w-full mx-auto font-mono">
      {/* Sub-navigation bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#0D1117] border border-slate-800/80 px-3 py-2 rounded">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400" />
          <span className="text-xs font-bold text-slate-200 tracking-wider uppercase">
            AI RESEARCH & EXPERIMENT WORKSTATION
          </span>
          <span className="text-[10px] text-slate-500 hidden sm:inline">
            // STABLE-BASELINES3 PPO × BOX2D LUNARLANDER-V3
          </span>
        </div>

        <TabNavigation
          tabs={tabs}
          activeTab={activeSubTab}
          onChange={(id) => setActiveSubTab(id as ResearchSubTab)}
          size="sm"
          ariaLabel="Research Sub-tabs"
        />
      </div>

      {/* Active Sub-tab Content */}
      <div className="flex-1 overflow-y-auto pr-1">
        {activeSubTab === 'benchmarks' && <BenchmarkMatrix />}
        {activeSubTab === 'outcomes' && (
          <div className="space-y-4">
            <OutcomeDistributionChart />
            <FailureAnalysisPanel />
          </div>
        )}
        {activeSubTab === 'robustness' && <EnvironmentalRobustnessView />}
        {activeSubTab === 'provenance' && <ProvenanceViewer />}
        {activeSubTab === 'analytics' && <AnalyticsShell />}
        {activeSubTab === 'specs' && <ExperimentContextCard />}
      </div>
    </div>
  );
};
