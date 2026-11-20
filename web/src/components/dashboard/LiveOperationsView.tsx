import React, { Suspense, lazy } from 'react';
import type {
  FlightMode,
  PolicyMode,
  SessionReadyPayload,
  SimulationSnapshotPayload,
} from '../../types/protocol';
import { SimulationCanvas } from '../SimulationCanvas';
import { TelemetryPanel } from '../TelemetryPanel';
import { FlightControls } from '../FlightControls';

// Code-split Three.js 3D viewport to keep initial 2D engineering bundle lean
const ThreeSimulationViewport = lazy(() =>
  import('../ThreeSimulationViewport').then((m) => ({
    default: m.ThreeSimulationViewport,
  }))
);

export interface LiveOperationsViewProps {
  viewMode: '2d' | '3d';
  onViewModeChange: (mode: '2d' | '3d') => void;
  interpolatedSnapshot: SimulationSnapshotPayload | null;
  latestSnapshot: SimulationSnapshotPayload | null;
  sessionReady: SessionReadyPayload | null;
  flightMode: FlightMode;
  policyMode: PolicyMode;
  isPaused: boolean;
  speedFactor: number;
  currentStep: number;
  latencyMs: number;
  hasDebrief: boolean;
  onReopenDebrief: () => void;
  onModeChange: (mode: FlightMode, policy?: PolicyMode) => void;
  onControlCmd: (command: 'pause' | 'resume' | 'reset' | 'set_speed', value?: number | null) => void;
  onSendAction: (step: number, action: 0 | 1 | 2 | 3) => void;
  onNavigateToResearch?: (subTab: 'analytics' | 'benchmarks' | 'outcomes' | 'robustness' | 'provenance' | 'specs') => void;
}

export const LiveOperationsView: React.FC<LiveOperationsViewProps> = ({
  viewMode,
  onViewModeChange,
  interpolatedSnapshot,
  latestSnapshot,
  sessionReady,
  flightMode,
  policyMode,
  isPaused,
  speedFactor,
  currentStep,
  latencyMs,
  hasDebrief,
  onReopenDebrief,
  onModeChange,
  onControlCmd,
  onSendAction,
  onNavigateToResearch,
}) => {
  const activeSnapshot = interpolatedSnapshot || latestSnapshot;

  return (
    <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 md:gap-4 max-w-[1920px] w-full mx-auto overflow-hidden font-mono">
      {/* Left / Center Viewport (8 Columns on Large Screens) */}
      <div className="lg:col-span-8 flex flex-col gap-2 min-h-[460px] h-[60vh] lg:h-[calc(100vh-95px)]">
        {/* Quick Viewport Switcher Toolbar */}
        <div className="flex items-center justify-between bg-[#0F141C] border border-slate-800 px-3 py-1.5 rounded-lg text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 text-[10px] uppercase font-bold">VIEWPORT MODE:</span>
            <span className="text-cyan-400 font-extrabold text-[11px]">
              {viewMode === '3d' ? '3D CINEMATIC AEROSPACE' : '2D ENGINEERING CANVAS'}
            </span>
            <span className="text-slate-600 text-[10px] hidden sm:inline">|</span>
            <span className="text-slate-400 text-[10px] hidden sm:inline">
              BOX2D 50 HZ // JITTER BUFFER INTERPOLATED
            </span>
          </div>

          <div className="flex items-center gap-2">
            {onNavigateToResearch && (
              <button
                type="button"
                onClick={() => onNavigateToResearch('analytics')}
                className="hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold bg-[#141B26] border border-cyan-500/40 text-cyan-400 hover:text-cyan-200 hover:border-cyan-400 transition-all shadow-[0_0_6px_rgba(0,240,255,0.15)]"
                title="View 4 Live Scientific Flight Charts"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <span>FLIGHT CHARTS (4)</span>
              </button>
            )}

            <div className="flex items-center gap-1 bg-[#141B26] p-0.5 rounded border border-slate-700">
              <button
                type="button"
                onClick={() => onViewModeChange('2d')}
                className={`px-2.5 py-0.5 rounded text-[10px] font-bold transition-all ${
                  viewMode === '2d'
                    ? 'bg-cyan-500 text-black shadow-[0_0_8px_rgba(0,240,255,0.4)]'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                2D HUD
              </button>
              <button
                type="button"
                onClick={() => onViewModeChange('3d')}
                className={`px-2.5 py-0.5 rounded text-[10px] font-bold transition-all ${
                  viewMode === '3d'
                    ? 'bg-cyan-500 text-black shadow-[0_0_8px_rgba(0,240,255,0.4)]'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                3D SCENE
              </button>
            </div>
          </div>
        </div>

        {/* Active Viewport Container */}
        <div className="flex-1 w-full h-full relative overflow-hidden">
          {viewMode === '3d' ? (
            <Suspense
              fallback={
                <div className="relative w-full h-full flex flex-col items-center justify-center p-6 bg-[#080B10] border border-cyan-500/20 rounded-lg font-mono text-center">
                  <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mb-3" />
                  <div className="text-cyan-400 font-bold text-xs tracking-wider">
                    INITIALIZING THREE.JS 3D VIEWPORT...
                  </div>
                </div>
              }
            >
              <ThreeSimulationViewport
                snapshot={activeSnapshot}
                sessionReady={sessionReady}
                flightMode={flightMode}
                hasDebrief={hasDebrief}
                onReopenDebrief={onReopenDebrief}
                onFallbackTo2D={() => onViewModeChange('2d')}
              />
            </Suspense>
          ) : (
            <SimulationCanvas
              snapshot={activeSnapshot}
              sessionReady={sessionReady}
              flightMode={flightMode}
              hasDebrief={hasDebrief}
              onReopenDebrief={onReopenDebrief}
            />
          )}
        </div>
      </div>

      {/* Right Sidebar: Controls & Telemetry (4 Columns on Large Screens) */}
      <div className="lg:col-span-4 flex flex-col gap-3 overflow-y-auto max-h-[calc(100vh-95px)] pr-0.5">
        {/* Flight Controls Panel */}
        <FlightControls
          flightMode={flightMode}
          policyMode={policyMode}
          isPaused={isPaused}
          speedFactor={speedFactor}
          currentStep={currentStep}
          onModeChange={onModeChange}
          onControlCmd={onControlCmd}
          onSendAction={onSendAction}
        />

        {/* Telemetry Readouts Panel */}
        <TelemetryPanel snapshot={latestSnapshot} latencyMs={latencyMs} />
      </div>
    </div>
  );
};
