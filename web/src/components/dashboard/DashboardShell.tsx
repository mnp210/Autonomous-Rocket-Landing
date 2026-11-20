import React, { useState } from 'react';
import type {
  ConnectionStatus,
} from '../../services/websocketClient';
import type {
  EpisodeCompletePayload,
  FlightMode,
  PolicyMode,
  SessionReadyPayload,
  SimulationSnapshotPayload,
} from '../../types/protocol';
import { MissionHeader } from './MissionHeader';
import { LiveOperationsView } from './LiveOperationsView';
import { ResearchDashboard, type ResearchSubTab } from './ResearchDashboard';
import { EpisodeDebriefModal } from '../EpisodeDebriefModal';
import { MissionBriefingModal } from '../MissionBriefingModal';

export interface DashboardShellProps {
  connectionStatus: ConnectionStatus;
  latencyMs: number;
  sessionId: string | null;
  errorMessage: string | null;
  onClearError: () => void;
  onReconnect: () => void;

  viewMode: '2d' | '3d';
  onViewModeChange: (mode: '2d' | '3d') => void;

  flightMode: FlightMode;
  policyMode: PolicyMode;
  isPaused: boolean;
  speedFactor: number;
  currentStep: number;

  sessionReady: SessionReadyPayload | null;
  latestSnapshot: SimulationSnapshotPayload | null;
  interpolatedSnapshot: SimulationSnapshotPayload | null;
  episodeComplete: EpisodeCompletePayload | null;
  showDebrief: boolean;

  onCloseDebrief: () => void;
  onReopenDebrief: () => void;
  onResetEpisode: () => void;
  onModeChange: (mode: FlightMode, policy?: PolicyMode) => void;
  onControlCmd: (command: 'pause' | 'resume' | 'reset' | 'set_speed', value?: number | null) => void;
  onSendAction: (step: number, action: 0 | 1 | 2 | 3) => void;
}

export const DashboardShell: React.FC<DashboardShellProps> = ({
  connectionStatus,
  latencyMs,
  sessionId,
  errorMessage,
  onClearError,
  onReconnect,
  viewMode,
  onViewModeChange,
  flightMode,
  policyMode,
  isPaused,
  speedFactor,
  currentStep,
  sessionReady,
  latestSnapshot,
  interpolatedSnapshot,
  episodeComplete,
  showDebrief,
  onCloseDebrief,
  onReopenDebrief,
  onResetEpisode,
  onModeChange,
  onControlCmd,
  onSendAction,
}) => {
  // Primary Navigation State: Live Operations vs Research Dashboard
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const initialDashboardTab =
    urlParams?.get('tab') === 'research' || urlParams?.get('view') === 'research'
      ? 'research'
      : 'operations';

  const [activeDashboardTab, setActiveDashboardTab] = useState<'operations' | 'research'>(
    initialDashboardTab
  );

  const [activeResearchSubTab, setActiveResearchSubTab] = useState<ResearchSubTab>(
    (urlParams?.get('subtab') as ResearchSubTab) || 'benchmarks'
  );

  // Mission Briefing state (Auto-shows for first-time visitors unless disabled via query param)
  const initialBriefing =
    urlParams?.get('briefing') === '1'
      ? true
      : urlParams?.get('briefing') === '0'
      ? false
      : typeof window !== 'undefined'
      ? localStorage.getItem('rocket_landing_briefing_seen') !== '1'
      : false;
  const [showBriefing, setShowBriefing] = useState<boolean>(initialBriefing);

  const handleNavigateToResearch = (subTab: ResearchSubTab = 'analytics') => {
    setActiveResearchSubTab(subTab);
    setActiveDashboardTab('research');
  };

  const hasDebrief =
    !showDebrief &&
    (episodeComplete !== null ||
      (latestSnapshot !== null &&
        (latestSnapshot.lifecycle.terminated || latestSnapshot.lifecycle.truncated)));

  return (
    <div className="min-h-screen bg-[#080B10] text-slate-100 flex flex-col font-mono selection:bg-cyan-500 selection:text-black">
      {/* 1. Aerospace Mission Header & Command Bar */}
      <MissionHeader
        activeView={activeDashboardTab}
        onViewChange={setActiveDashboardTab}
        viewMode={viewMode}
        onViewModeChange={onViewModeChange}
        connectionStatus={connectionStatus}
        latencyMs={latencyMs}
        sessionId={sessionId}
        flightMode={flightMode}
        onReconnect={onReconnect}
        onOpenBriefing={() => setShowBriefing(true)}
      />

      {/* 2. System Alert / Error Toast Banner */}
      {errorMessage && (
        <div className="bg-rose-950/90 border-b border-rose-500 text-rose-200 px-4 py-2 text-xs flex justify-between items-center shadow-lg animate-in slide-in-from-top-2">
          <div className="flex items-center gap-2">
            <span className="text-rose-400 font-bold">⚠️ SYSTEM NOTICE:</span>
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={onClearError}
            className="text-rose-400 hover:text-white font-bold ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* 3. Main Operational Viewport or Research Workstation */}
      <main className="flex-1 p-3 md:p-4 flex flex-col overflow-hidden">
        {activeDashboardTab === 'operations' ? (
          <LiveOperationsView
            viewMode={viewMode}
            onViewModeChange={onViewModeChange}
            interpolatedSnapshot={interpolatedSnapshot}
            latestSnapshot={latestSnapshot}
            sessionReady={sessionReady}
            flightMode={flightMode}
            policyMode={policyMode}
            isPaused={isPaused}
            speedFactor={speedFactor}
            currentStep={currentStep}
            latencyMs={latencyMs}
            hasDebrief={hasDebrief}
            onReopenDebrief={onReopenDebrief}
            onModeChange={onModeChange}
            onControlCmd={onControlCmd}
            onSendAction={onSendAction}
            onNavigateToResearch={handleNavigateToResearch}
          />
        ) : (
          <ResearchDashboard
            activeSubTab={activeResearchSubTab}
            onSubTabChange={setActiveResearchSubTab}
          />
        )}
      </main>

      {/* 4. Episode Debrief Modal */}
      {showDebrief && (
        <EpisodeDebriefModal
          completeData={episodeComplete}
          latestSnapshot={latestSnapshot}
          onDismiss={onCloseDebrief}
          onReset={onResetEpisode}
        />
      )}

      {/* 5. Visitor Mission Briefing Modal */}
      <MissionBriefingModal
        isOpen={showBriefing}
        onClose={() => setShowBriefing(false)}
        onOpenResearch={() => handleNavigateToResearch('benchmarks')}
      />
    </div>
  );
};
