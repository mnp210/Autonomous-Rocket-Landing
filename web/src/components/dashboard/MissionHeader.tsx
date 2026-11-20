import React from 'react';
import type { ConnectionStatus } from '../../services/websocketClient';
import type { FlightMode } from '../../types/protocol';
import { TabNavigation } from '../common/TabNavigation';

export interface MissionHeaderProps {
  activeView: 'operations' | 'research';
  onViewChange: (view: 'operations' | 'research') => void;
  viewMode: '2d' | '3d';
  onViewModeChange: (mode: '2d' | '3d') => void;
  connectionStatus: ConnectionStatus;
  latencyMs: number;
  sessionId: string | null;
  flightMode: FlightMode;
  onReconnect: () => void;
  onOpenBriefing?: () => void;
}

export const MissionHeader: React.FC<MissionHeaderProps> = ({
  activeView,
  onViewChange,
  viewMode,
  onViewModeChange,
  connectionStatus,
  latencyMs,
  sessionId,
  flightMode,
  onReconnect,
  onOpenBriefing,
}) => {
  const isConnected = connectionStatus === 'CONNECTED';
  const isReconnecting = connectionStatus === 'RECONNECTING' || connectionStatus === 'CONNECTING';

  const viewTabs = [
    {
      id: 'operations',
      label: 'LIVE OPERATIONS',
      badge: viewMode.toUpperCase(),
    },
    {
      id: 'research',
      label: 'RESEARCH & BENCHMARKS',
      badge: 'EXPLORATORY',
    },
  ];

  return (
    <header className="bg-[#0B0E14] border-b border-slate-800/90 px-3 md:px-4 py-2 flex flex-wrap items-center justify-between gap-3 font-mono text-xs select-none">
      {/* 1. Branding & Mission Identity */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-cyan-950/80 border border-cyan-400 flex items-center justify-center text-cyan-300 font-extrabold text-sm shadow-[0_0_8px_rgba(0,240,255,0.4)]">
          🚀
        </div>

        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-slate-100 font-bold text-sm tracking-wider">
              AUTONOMOUS ROCKET LANDING
            </h1>
            <span className="bg-cyan-950/60 text-cyan-400 border border-cyan-500/40 px-1.5 py-0.5 rounded text-[10px] font-semibold">
              STAGE 9.4 // RESEARCH & OPS
            </span>
          </div>
          <div className="text-slate-500 text-[10px] flex items-center gap-2 mt-0.5">
            <span>PPO STAGE D (SEED 42)</span>
            <span>•</span>
            <span>BOX2D 50 HZ ENGINE</span>
            <span>•</span>
            <span className="text-cyan-400 font-bold">
              {flightMode === 'ai' ? 'AUTONOMOUS' : 'MANUAL PILOT'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Primary Navigation: Live Operations vs Research */}
      <div className="flex items-center gap-2">
        <TabNavigation
          tabs={viewTabs}
          activeTab={activeView}
          onChange={(tabId) => onViewChange(tabId as 'operations' | 'research')}
          size="md"
          ariaLabel="Primary Dashboard Views"
        />

        {/* Viewport Mode Quick Selector (only relevant during Live Operations) */}
        {activeView === 'operations' && (
          <div className="hidden sm:flex items-center bg-[#131822] border border-slate-800 rounded p-0.5">
            <button
              type="button"
              onClick={() => onViewModeChange('2d')}
              className={`px-2.5 py-1 rounded text-[10px] font-bold transition-all ${
                viewMode === '2d'
                  ? 'bg-cyan-950 border border-cyan-400 text-cyan-300 shadow-[0_0_8px_rgba(0,240,255,0.4)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              2D HUD
            </button>
            <button
              type="button"
              onClick={() => onViewModeChange('3d')}
              className={`px-2.5 py-1 rounded text-[10px] font-bold transition-all ${
                viewMode === '3d'
                  ? 'bg-cyan-950 border border-cyan-400 text-cyan-300 shadow-[0_0_8px_rgba(0,240,255,0.4)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              3D SCENE
            </button>
          </div>
        )}
      </div>

      {/* 3. Server Connection, Briefing & Latency Telemetry */}
      <div className="flex items-center gap-2">
        {onOpenBriefing && (
          <button
            type="button"
            onClick={onOpenBriefing}
            className="flex items-center gap-1 bg-[#131822] hover:bg-cyan-950/60 border border-slate-700 hover:border-cyan-400 px-2.5 py-1 rounded text-[10px] text-cyan-300 font-bold transition-all shadow-[0_0_8px_rgba(0,240,255,0.15)]"
            title="Open Mission Briefing & Capabilities Overview"
          >
            <span>ℹ️</span>
            <span>BRIEFING</span>
          </button>
        )}

        {sessionId && (
          <div className="hidden lg:flex items-center gap-1.5 bg-[#131822] border border-slate-800 px-2 py-1 rounded text-[10px] text-slate-400">
            <span className="text-slate-600">SESSION:</span>
            <span className="text-slate-300">{sessionId.slice(0, 8)}...</span>
          </div>
        )}

        {/* Live WebSocket Status */}
        <div className="flex items-center gap-2 bg-[#131822] border border-slate-800 px-2.5 py-1 rounded">
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected
                ? 'bg-emerald-400 shadow-[0_0_6px_#00E676]'
                : isReconnecting
                ? 'bg-amber-400 animate-ping'
                : 'bg-rose-500'
            }`}
          />
          <span
            className={`text-[10px] font-bold tracking-wider ${
              isConnected
                ? 'text-emerald-400'
                : isReconnecting
                ? 'text-amber-400'
                : 'text-rose-400'
            }`}
          >
            {connectionStatus}
          </span>
          {isConnected && (
            <span className="text-slate-500 text-[10px] tabular-nums font-semibold border-l border-slate-700 pl-2">
              {latencyMs}ms
            </span>
          )}
        </div>

        {/* Manual Reconnect Action if Disconnected */}
        {!isConnected && !isReconnecting && (
          <button
            type="button"
            onClick={onReconnect}
            className="px-2.5 py-1 bg-rose-950/80 hover:bg-rose-900 border border-rose-500/80 text-rose-300 text-[10px] font-bold rounded transition-colors"
          >
            RECONNECT
          </button>
        )}
      </div>
    </header>
  );
};
