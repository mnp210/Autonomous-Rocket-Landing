/**
 * Engineering Console Header Bar.
 *
 * Displays aerospace mission branding, model verification tags,
 * view mode selector (2D Engineering vs 3D Cinematic), real-time
 * WebSocket connection state, and round-trip latency.
 */

import React from 'react';
import type { ConnectionStatus } from '../services/websocketClient';

interface HeaderProps {
  connectionStatus: ConnectionStatus;
  latencyMs: number;
  sessionId: string | null;
  viewMode: '2d' | '3d';
  onViewModeChange: (mode: '2d' | '3d') => void;
  onReconnect: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  connectionStatus,
  latencyMs,
  sessionId,
  viewMode,
  onViewModeChange,
  onReconnect,
}) => {
  const isConnected = connectionStatus === 'CONNECTED';
  const isReconnecting = connectionStatus === 'RECONNECTING' || connectionStatus === 'CONNECTING';

  return (
    <header className="bg-[#0B0E14] border-b border-slate-800 px-4 py-2 flex flex-wrap items-center justify-between gap-3 font-mono text-xs select-none">
      {/* Title & Metadata */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-cyan-950/80 border border-cyan-400 flex items-center justify-center text-cyan-300 font-extrabold text-sm shadow-[0_0_8px_rgba(0,240,255,0.4)]">
          🚀
        </div>

        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-slate-100 font-bold text-sm tracking-wider">
              AUTONOMOUS ROCKET LANDING
            </h1>
            <span className="bg-cyan-950/60 text-cyan-400 border border-cyan-500/40 px-1.5 py-0.2 rounded text-[10px] font-semibold">
              STAGE 9.3 // HYBRID 2D/3D
            </span>
          </div>
          <div className="text-slate-500 text-[10px] flex items-center gap-2 mt-0.5">
            <span>MODEL: PPO CURRICULUM STAGE D (SEED 42)</span>
            <span>•</span>
            <span>BOX2D 50 HZ PHYSICS ENGINE</span>
          </div>
        </div>
      </div>

      {/* Center: 2D Engineering / 3D Cinematic View Selector */}
      <div className="flex items-center bg-[#131822] border border-slate-800 rounded p-0.5">
        <button
          type="button"
          onClick={() => onViewModeChange('2d')}
          className={`px-3 py-1 rounded text-[11px] font-bold transition-all flex items-center gap-1.5 ${
            viewMode === '2d'
              ? 'bg-cyan-950 border border-cyan-400 text-cyan-300 shadow-[0_0_8px_rgba(0,240,255,0.4)]'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>📐</span>
          <span>2D ENGINEERING</span>
        </button>

        <button
          type="button"
          onClick={() => onViewModeChange('3d')}
          className={`px-3 py-1 rounded text-[11px] font-bold transition-all flex items-center gap-1.5 ${
            viewMode === '3d'
              ? 'bg-cyan-950 border border-cyan-400 text-cyan-300 shadow-[0_0_8px_rgba(0,240,255,0.4)]'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>🌌</span>
          <span>3D CINEMATIC</span>
        </button>
      </div>

      {/* Connection & Network Status */}
      <div className="flex items-center gap-2.5">
        {sessionId && (
          <div className="hidden md:flex items-center gap-1.5 bg-[#131822] border border-slate-800 px-2 py-1 rounded text-[10px] text-slate-400">
            <span className="text-slate-600">SESSION:</span>
            <span className="text-slate-300">{sessionId.slice(0, 8)}...</span>
          </div>
        )}

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
            className={`font-bold text-[10px] tracking-wide ${
              isConnected ? 'text-emerald-400' : isReconnecting ? 'text-amber-400' : 'text-rose-400'
            }`}
          >
            {connectionStatus}
          </span>

          {isConnected && (
            <span className="text-slate-500 text-[10px] ml-1 pl-1.5 border-l border-slate-700">
              {latencyMs}ms RTT
            </span>
          )}
        </div>

        {!isConnected && (
          <button
            type="button"
            onClick={onReconnect}
            className="py-1 px-2.5 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-bold text-[10px] transition-colors shadow-[0_0_8px_rgba(0,240,255,0.4)]"
          >
            RECONNECT
          </button>
        )}
      </div>
    </header>
  );
};
