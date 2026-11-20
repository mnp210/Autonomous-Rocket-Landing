/**
 * Mission Briefing Modal.
 *
 * Provides a comprehensive, honest, and welcoming onboarding briefing for
 * new visitors and researchers. Explains what the project is, the Box2D/PPO
 * simulation reality, interactive capabilities, and controls.
 */

import React, { useState } from 'react';
import { StatusBadge } from './common/StatusBadge';

interface MissionBriefingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenResearch?: () => void;
}

export const MissionBriefingModal: React.FC<MissionBriefingModalProps> = ({
  isOpen,
  onClose,
  onOpenResearch,
}) => {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  if (!isOpen) return null;

  const handleClose = () => {
    if (dontShowAgain && typeof window !== 'undefined') {
      try {
        localStorage.setItem('rocket_landing_briefing_seen', '1');
      } catch {
        // Ignore localStorage restrictions
      }
    }
    onClose();
  };

  const handleGoToResearch = () => {
    handleClose();
    if (onOpenResearch) {
      onOpenResearch();
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="briefing-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 font-mono select-none animate-in fade-in duration-200"
    >
      <div className="bg-[#0D1117] border border-cyan-500/40 rounded-xl max-w-2xl w-full p-5 shadow-[0_0_50px_rgba(0,240,255,0.15)] flex flex-col gap-4 text-xs text-slate-300 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-cyan-950/80 border border-cyan-400 flex items-center justify-center text-cyan-300 font-extrabold text-base shadow-[0_0_10px_rgba(0,240,255,0.4)]">
              🚀
            </div>
            <div>
              <h2 id="briefing-title" className="text-sm font-bold text-slate-100 tracking-wider">
                MISSION BRIEFING // AUTONOMOUS ROCKET LANDING
              </h2>
              <span className="text-[10px] text-slate-500">
                DEEP REINFORCEMENT LEARNING FLIGHT-TEST & RESEARCH BENCHMARK
              </span>
            </div>
          </div>

          <StatusBadge label="OPERATIONAL" variant="nominal" size="sm" />
        </div>

        {/* 1. Core Purpose & Technical Truth */}
        <div className="p-3 rounded bg-[#131822] border border-slate-800 space-y-2 leading-relaxed">
          <span className="text-cyan-400 font-bold block text-[11px] uppercase tracking-wider">
            PROJECT OVERVIEW & SIMULATION REALITY
          </span>
          <p className="text-[11px] text-slate-300">
            This application demonstrates autonomous precision rocket landings controlled by deep reinforcement learning. All physical dynamics step continuously at <strong>50 Hz</strong> on an authoritative Python server running <strong>Box2D</strong> (<code className="text-cyan-300">Gymnasium LunarLander-v3</code>) with specialized aerodynamic disturbances, domain randomization, and terminal contact latches.
          </p>
          <div className="p-2 rounded bg-[#090D14] border border-amber-500/30 text-[10px] text-amber-300/90">
            ⚠️ <strong>AEROSPACE CLARIFICATION:</strong> This is an algorithmic reinforcement learning research workstation, not a certified aerospace flight simulator or 6-DOF orbital trajectory engine. All coordinates are rendered in authentic Box2D simulation units (<code className="text-amber-200">u</code>, <code className="text-amber-200">u/s</code>).
          </div>
        </div>

        {/* 2. Key Interactive Capabilities */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
          <div className="p-2.5 rounded bg-[#101622] border border-slate-800/80 space-y-1">
            <span className="font-bold text-slate-200 flex items-center gap-1.5">
              🤖 <span>AUTONOMOUS PPO FLIGHT</span>
            </span>
            <p className="text-[10px] text-slate-400 leading-normal">
              Observe the trained policy network (<code className="text-cyan-400">MlpPolicy [64, 64]</code>) calculate optimal continuous descent trajectories, engine throttling, and RCS attitude correction.
            </p>
          </div>

          <div className="p-2.5 rounded bg-[#101622] border border-slate-800/80 space-y-1">
            <span className="font-bold text-slate-200 flex items-center gap-1.5">
              🕹️ <span>MANUAL PILOT TAKEOVER</span>
            </span>
            <p className="text-[10px] text-slate-400 leading-normal">
              Switch to manual control at any point. Use <strong className="text-cyan-300">W / ↑</strong> (Main Engine), <strong className="text-cyan-300">A / ←</strong> (Left RCS), and <strong className="text-cyan-300">D / →</strong> (Right RCS) to pilot the rocket yourself.
            </p>
          </div>

          <div className="p-2.5 rounded bg-[#101622] border border-slate-800/80 space-y-1">
            <span className="font-bold text-slate-200 flex items-center gap-1.5">
              🪐 <span>2D HUD & 3D PRESENTATION</span>
            </span>
            <p className="text-[10px] text-slate-400 leading-normal">
              Toggle between the <strong>2D Engineering HUD</strong> and <strong>3D WebGL Spaceport</strong> during the active flight without interrupting physics or restarting the session.
            </p>
          </div>

          <div className="p-2.5 rounded bg-[#101622] border border-slate-800/80 space-y-1">
            <span className="font-bold text-slate-200 flex items-center gap-1.5">
              📈 <span>4 LIVE CHARTS & RESEARCH DATA</span>
            </span>
            <p className="text-[10px] text-slate-400 leading-normal">
              Stream live Trajectory, Braking Corridor, Reward, and Attitude charts, or explore forensic benchmark data from 12 production runs (9,600 verified evaluation episodes).
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-slate-800">
          <label className="flex items-center gap-2 text-[10px] text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
            />
            <span>Don't show this briefing automatically on next visit</span>
          </label>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            {onOpenResearch && (
              <button
                type="button"
                onClick={handleGoToResearch}
                className="flex-1 sm:flex-initial py-2 px-3 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-bold transition-all text-xs"
              >
                📊 EXPLORE RESEARCH DATA
              </button>
            )}

            <button
              type="button"
              onClick={handleClose}
              className="flex-1 sm:flex-initial py-2 px-4 rounded bg-cyan-500 hover:bg-cyan-400 text-black font-extrabold transition-all shadow-[0_0_15px_rgba(0,240,255,0.4)] text-xs flex items-center justify-center gap-1.5"
            >
              🚀 ENTER LIVE OPERATIONS
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
