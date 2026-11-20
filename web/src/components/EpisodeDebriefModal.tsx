/**
 * Episode Debrief Modal.
 *
 * Appears upon episode termination or truncation, presenting authoritative
 * touchdown metrics, impact dynamics, criteria verifications, and outcome classification.
 */

import React from 'react';
import type { EpisodeCompletePayload, SimulationSnapshotPayload } from '../types/protocol';

interface EpisodeDebriefModalProps {
  completeData: EpisodeCompletePayload | null;
  latestSnapshot: SimulationSnapshotPayload | null;
  onDismiss: () => void;
  onReset: () => void;
}

export const EpisodeDebriefModal: React.FC<EpisodeDebriefModalProps> = ({
  completeData,
  latestSnapshot,
  onDismiss,
  onReset,
}) => {
  if (
    !completeData &&
    (!latestSnapshot ||
      (!latestSnapshot.lifecycle.terminated && !latestSnapshot.lifecycle.truncated))
  ) {
    return null;
  }

  // Derive metrics from completeData or fallback to latestSnapshot
  const rawOutcome = (
    completeData?.outcome ||
    latestSnapshot?.lifecycle.outcome ||
    'TERMINATED'
  ).toUpperCase();

  const totalSteps = completeData?.total_steps ?? latestSnapshot?.lifecycle.step ?? 0;
  const simTime = completeData?.total_sim_time ?? latestSnapshot?.lifecycle.sim_time ?? 0.0;
  const reward = completeData?.cumulative_reward ?? latestSnapshot?.lifecycle.cumulative_reward ?? 0.0;

  const impactVx = completeData?.impact_vel_x ?? latestSnapshot?.impact.impact_vel_x;
  const impactVy = completeData?.impact_vel_y ?? latestSnapshot?.impact.impact_vel_y;
  const impactTilt =
    completeData?.impact_tilt_deg ??
    (latestSnapshot?.impact.impact_tilt ? latestSnapshot.impact.impact_tilt * 57.2958 : null);

  const finalClearance = completeData?.final_clearance ?? latestSnapshot?.kinematics.altitude ?? 0.0;
  const finalTilt =
    completeData?.final_tilt_deg ??
    (latestSnapshot ? latestSnapshot.kinematics.angle * 57.2958 : 0.0);

  // Outcome Classification
  const isSuccess = rawOutcome.includes('SUCCESS');
  const isCrash = rawOutcome.includes('CRASH') || rawOutcome.includes('FAILED');
  const isTimeout = rawOutcome.includes('TIMEOUT') || (!isSuccess && !isCrash && totalSteps >= 1000);

  let bannerBg = 'bg-slate-900 border-slate-700 text-slate-200';
  let bannerTitle = 'MISSION TERMINATED';
  let bannerSubtitle = 'Episode completed under authoritative environment criteria.';
  let badgeColor = 'text-slate-400 border-slate-700';

  if (isSuccess) {
    bannerBg = 'bg-emerald-950/90 border-emerald-500 text-emerald-200 shadow-[0_0_20px_rgba(0,230,118,0.25)]';
    bannerTitle = 'MISSION ACCOMPLISHED // TOUCHDOWN NOMINAL';
    bannerSubtitle = 'Rocket stably settled on target pad with upright attitude and safe sink rate.';
    badgeColor = 'text-emerald-400 border-emerald-500 bg-emerald-950/80';
  } else if (isCrash) {
    bannerBg = 'bg-rose-950/90 border-rose-500 text-rose-200 shadow-[0_0_20px_rgba(255,23,68,0.25)]';
    bannerTitle = 'CRITICAL FAILURE // VEHICLE LOSS';
    bannerSubtitle = 'Excessive structural impact velocity, angular pitch deviation, or hull ground strike.';
    badgeColor = 'text-rose-400 border-rose-500 bg-rose-950/80';
  } else if (isTimeout) {
    bannerBg = 'bg-amber-950/90 border-amber-500 text-amber-200 shadow-[0_0_20px_rgba(255,179,0,0.25)]';
    bannerTitle = 'MISSION TIMEOUT // PROPELLANT EXHAUSTION';
    bannerSubtitle = '1,000-step flight duration limit reached before achieving stable dual-leg touchdown.';
    badgeColor = 'text-amber-400 border-amber-500 bg-amber-950/80';
  }

  // Diagnostic Checklist
  const sinkRateCheck = impactVy !== null && impactVy !== undefined ? Math.abs(impactVy) <= 1.2 : null;
  const attitudeCheck = impactTilt !== null && impactTilt !== undefined ? Math.abs(impactTilt) <= 12.0 : null;
  const clearanceCheck = finalClearance <= 0.05;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 font-mono select-none">
      <div className="bg-[#0B0E14] border border-slate-700 rounded-xl max-w-lg w-full p-5 shadow-2xl flex flex-col gap-3.5 animate-in fade-in zoom-in-95 duration-150">
        {/* Outcome Header Banner */}
        <div className={`p-4 rounded-lg border ${bannerBg}`}>
          <div className="text-[11px] uppercase tracking-widest font-semibold flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span>🚀</span>
              <span>EPISODE FLIGHT DEBRIEF</span>
            </span>
            <span className={`px-2 py-0.5 rounded border text-[10px] font-bold ${badgeColor}`}>
              {rawOutcome}
            </span>
          </div>
          <div className="text-base font-black mt-1 tracking-wide">{bannerTitle}</div>
          <div className="text-xs opacity-90 mt-1">{bannerSubtitle}</div>
        </div>

        {/* Diagnostic Criteria Report */}
        <div className="grid grid-cols-3 gap-1.5 text-[10px] bg-[#141B26] p-2.5 rounded border border-slate-800">
          <div className="text-center">
            <div className="text-slate-400">SINK RATE</div>
            <div className={`font-bold mt-0.5 ${sinkRateCheck === null ? 'text-slate-400' : sinkRateCheck ? 'text-emerald-400' : 'text-rose-400'}`}>
              {sinkRateCheck === null ? 'N/A' : sinkRateCheck ? 'PASS (≤1.2 u/s)' : 'EXCESSIVE'}
            </div>
          </div>
          <div className="text-center border-x border-slate-800">
            <div className="text-slate-400">ATTITUDE</div>
            <div className={`font-bold mt-0.5 ${attitudeCheck === null ? 'text-slate-400' : attitudeCheck ? 'text-emerald-400' : 'text-rose-400'}`}>
              {attitudeCheck === null ? 'N/A' : attitudeCheck ? 'PASS (≤12°)' : 'EXCURSION'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-slate-400">PAD SETTLED</div>
            <div className={`font-bold mt-0.5 ${clearanceCheck ? 'text-emerald-400' : 'text-amber-400'}`}>
              {clearanceCheck ? 'PASS (ON PAD)' : 'OFF PAD'}
            </div>
          </div>
        </div>

        {/* Telemetry Breakdown Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-[#131822] p-2.5 rounded border border-slate-800">
            <span className="text-slate-400 text-[10px]">TOTAL FLIGHT TIME</span>
            <div className="text-sm font-bold text-slate-200 mt-0.5">
              {simTime.toFixed(2)}s <span className="text-slate-500 text-xs font-normal">({totalSteps} steps)</span>
            </div>
          </div>

          <div className="bg-[#131822] p-2.5 rounded border border-slate-800">
            <span className="text-slate-400 text-[10px]">CUMULATIVE REWARD</span>
            <div className={`text-sm font-extrabold mt-0.5 ${reward >= 200 ? 'text-emerald-400' : reward >= 0 ? 'text-cyan-400' : 'text-rose-400'}`}>
              {reward >= 0 ? `+${reward.toFixed(1)}` : reward.toFixed(1)}
            </div>
          </div>

          <div className="bg-[#131822] p-2.5 rounded border border-slate-800">
            <span className="text-slate-400 text-[10px]">TOUCHDOWN VELOCITY (Vx / Vy)</span>
            <div className="text-sm font-bold text-slate-200 mt-0.5">
              {impactVx !== null && impactVx !== undefined ? `${impactVx.toFixed(2)}` : '0.00'} u/s &nbsp;/&nbsp;{' '}
              {impactVy !== null && impactVy !== undefined ? `${impactVy.toFixed(2)}` : '0.00'} u/s
            </div>
          </div>

          <div className="bg-[#131822] p-2.5 rounded border border-slate-800">
            <span className="text-slate-400 text-[10px]">TOUCHDOWN ATTITUDE</span>
            <div className="text-sm font-bold text-slate-200 mt-0.5">
              {impactTilt !== null && impactTilt !== undefined ? `${impactTilt.toFixed(1)}°` : '0.0°'}
            </div>
          </div>

          <div className="bg-[#131822] p-2.5 rounded border border-slate-800">
            <span className="text-slate-400 text-[10px]">FINAL PAD CLEARANCE</span>
            <div className="text-sm font-bold text-cyan-300 mt-0.5">
              {finalClearance.toFixed(3)} <span className="text-slate-500 text-[10px] font-normal">units</span>
            </div>
          </div>

          <div className="bg-[#131822] p-2.5 rounded border border-slate-800">
            <span className="text-slate-400 text-[10px]">FINAL RESTING TILT</span>
            <div className="text-sm font-bold text-slate-200 mt-0.5">
              {finalTilt.toFixed(1)}°
            </div>
          </div>
        </div>

        {/* Modal Action Buttons */}
        <div className="flex gap-2.5 pt-2 border-t border-slate-800">
          <button
            type="button"
            onClick={onDismiss}
            className="flex-1 py-2 px-3 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition-colors border border-slate-700"
          >
            👁️ INSPECT FINAL RESTING STATE
          </button>

          <button
            type="button"
            onClick={onReset}
            className="flex-1 py-2 px-3 rounded bg-cyan-500 hover:bg-cyan-400 text-black text-xs font-extrabold transition-colors shadow-[0_0_14px_rgba(0,240,255,0.5)]"
          >
            🔄 NEXT EPISODE (RESET)
          </button>
        </div>
      </div>
    </div>
  );
};
