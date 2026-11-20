/**
 * Monospace Engineering Telemetry Panel.
 *
 * Displays authoritative primary flight data, propulsion states,
 * ground contact sensors, and reward metrics with high visual hierarchy.
 * All units are strictly honest:
 * - Position & Distances: Box2D simulation units ('units' or 'u')
 * - Velocities: Box2D simulation units per second ('u/s')
 * - Angles: Degrees ('°') and Angular velocity ('°/s')
 */

import React from 'react';
import type { SimulationSnapshotPayload } from '../types/protocol';

interface TelemetryPanelProps {
  snapshot: SimulationSnapshotPayload | null;
  latencyMs: number;
}

export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({ snapshot, latencyMs }) => {
  if (!snapshot) {
    return (
      <div className="bg-[#0F141C] border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-500 shadow-xl">
        INITIALIZING SENSORS & TELEMETRY STREAM...
      </div>
    );
  }

  const { kinematics: k, propulsion: p, landing_gear: g, atmosphere: a, lifecycle: l } = snapshot;

  const tiltDeg = k.angle * 57.2957795; // rad to deg
  const angVelDeg = k.ang_vel * 57.2957795;

  // Safe landing criteria threshold checks
  const safeDescent = Math.abs(k.vel_y) <= 1.0;
  const cautionDescent = Math.abs(k.vel_y) > 1.0 && Math.abs(k.vel_y) <= 2.0;
  const safeTilt = Math.abs(tiltDeg) <= 10.0;
  const safeHorizontal = Math.abs(k.vel_x) <= 0.8;
  const onPad = Math.abs(k.pos_x) <= 1.5;

  return (
    <div className="bg-[#0F141C] border border-slate-800 rounded-lg p-3 font-mono text-xs flex flex-col gap-2.5 shadow-2xl">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <span className="text-cyan-400 font-bold tracking-wider flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          PRIMARY FLIGHT TELEMETRY
        </span>
        <span className="text-slate-400 text-[10px]">
          RTT: <span className={latencyMs < 30 ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>{latencyMs}ms</span>
        </span>
      </div>

      {/* Grid: 2 Columns for Flight Dynamics */}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        {/* Altitude / Clearance */}
        <div className="bg-[#141B26] p-2 rounded border border-slate-800/80">
          <div className="text-slate-400 text-[10px] uppercase flex justify-between">
            <span>PAD CLEARANCE</span>
            <span className={k.altitude <= 0.05 ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
              {k.altitude <= 0.05 ? 'GROUND' : 'DESCENT'}
            </span>
          </div>
          <div className="text-lg font-extrabold text-cyan-300 mt-0.5">
            {k.altitude.toFixed(2)} <span className="text-[10px] text-slate-500 font-normal">units</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">CoM Y: {k.pos_y.toFixed(2)}u</div>
        </div>

        {/* Target Offset X */}
        <div className="bg-[#141B26] p-2 rounded border border-slate-800/80">
          <div className="text-slate-400 text-[10px] uppercase flex justify-between">
            <span>PAD OFFSET (X)</span>
            <span className={onPad ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
              {onPad ? 'ON PAD' : 'OFF AXIS'}
            </span>
          </div>
          <div className={`text-lg font-extrabold mt-0.5 ${onPad ? 'text-emerald-400' : 'text-amber-400'}`}>
            {k.pos_x >= 0 ? `+${k.pos_x.toFixed(2)}` : k.pos_x.toFixed(2)}{' '}
            <span className="text-[10px] text-slate-500 font-normal">units</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">PAD BOUNDS: ±2.0u</div>
        </div>

        {/* Vertical Velocity */}
        <div className="bg-[#141B26] p-2 rounded border border-slate-800/80">
          <div className="text-slate-400 text-[10px] uppercase flex justify-between">
            <span>VERT VELOCITY (Vy)</span>
            <span className={safeDescent ? 'text-emerald-400' : cautionDescent ? 'text-amber-400' : 'text-rose-400'}>
              {safeDescent ? 'NOMINAL' : cautionDescent ? 'CAUTION' : 'DANGER'}
            </span>
          </div>
          <div
            className={`text-base font-extrabold mt-0.5 ${
              safeDescent ? 'text-emerald-400' : cautionDescent ? 'text-amber-400' : 'text-rose-400'
            }`}
          >
            {k.vel_y >= 0 ? `+${k.vel_y.toFixed(2)}` : k.vel_y.toFixed(2)}{' '}
            <span className="text-[10px] text-slate-500 font-normal">u/s</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">
            LIMIT: ≤ 1.00 u/s (SINK)
          </div>
        </div>

        {/* Horizontal Velocity */}
        <div className="bg-[#141B26] p-2 rounded border border-slate-800/80">
          <div className="text-slate-400 text-[10px] uppercase flex justify-between">
            <span>HORIZ VELOCITY (Vx)</span>
            <span className={safeHorizontal ? 'text-emerald-400' : 'text-amber-400'}>
              {safeHorizontal ? 'STABLE' : 'DRIFT'}
            </span>
          </div>
          <div className={`text-base font-extrabold mt-0.5 ${safeHorizontal ? 'text-emerald-400' : 'text-amber-400'}`}>
            {k.vel_x >= 0 ? `+${k.vel_x.toFixed(2)}` : k.vel_x.toFixed(2)}{' '}
            <span className="text-[10px] text-slate-500 font-normal">u/s</span>
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">
            LIMIT: ≤ 0.80 u/s
          </div>
        </div>

        {/* Attitude Tilt */}
        <div className="bg-[#141B26] p-2 rounded border border-slate-800/80">
          <div className="text-slate-400 text-[10px] uppercase flex justify-between">
            <span>ATTITUDE TILT</span>
            <span className={safeTilt ? 'text-emerald-400' : 'text-rose-400'}>
              {safeTilt ? 'UPRIGHT' : 'TILT WARNING'}
            </span>
          </div>
          <div className={`text-base font-extrabold mt-0.5 ${safeTilt ? 'text-emerald-400' : 'text-rose-400'}`}>
            {tiltDeg >= 0 ? `+${tiltDeg.toFixed(1)}°` : `${tiltDeg.toFixed(1)}°`}
          </div>
          <div className="text-[9px] text-slate-500 mt-0.5">RATE: {angVelDeg.toFixed(1)}°/s</div>
        </div>

        {/* Step & Simulation Time */}
        <div className="bg-[#141B26] p-2 rounded border border-slate-800/80">
          <div className="text-slate-400 text-[10px] uppercase flex justify-between">
            <span>MISSION PROGRESS</span>
            <span className="text-cyan-400">{l.step}/1000</span>
          </div>
          <div className="text-base font-extrabold text-slate-200 mt-0.5">
            {l.sim_time.toFixed(2)}s <span className="text-[10px] text-slate-500 font-normal">(50 Hz)</span>
          </div>
          <div className="text-[9px] text-cyan-400/90 mt-0.5 font-bold">
            REWARD: {l.cumulative_reward >= 0 ? `+${l.cumulative_reward.toFixed(1)}` : l.cumulative_reward.toFixed(1)}
          </div>
        </div>
      </div>

      {/* Propulsion Actuator Section */}
      <div className="bg-[#141B26] p-2.5 rounded border border-slate-800/80 flex flex-col gap-2">
        <div className="text-slate-400 text-[10px] font-semibold flex justify-between">
          <span>PROPULSION ACTUATORS</span>
          <span className="text-cyan-400 font-bold">
            {p.action === 0 && 'ACTION 0: COAST / CUTOFF'}
            {p.action === 1 && 'ACTION 1: PORT RCS [LEFT]'}
            {p.action === 2 && 'ACTION 2: MAIN ENGINE'}
            {p.action === 3 && 'ACTION 3: STBD RCS [RIGHT]'}
          </span>
        </div>

        {/* Main Engine Throttle Bar */}
        <div>
          <div className="flex justify-between text-[10px] text-slate-400 mb-1">
            <span>MAIN ENGINE THROTTLE</span>
            <span className={p.throttle > 0 ? 'text-amber-400 font-bold' : 'text-slate-500'}>
              {(p.throttle * 100).toFixed(0)}%
            </span>
          </div>
          <div className="w-full bg-slate-900 h-2.5 rounded overflow-hidden border border-slate-700">
            <div
              className="bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 h-full transition-all duration-75"
              style={{ width: `${Math.max(0, Math.min(100, p.throttle * 100))}%` }}
            />
          </div>
        </div>

        {/* RCS Thruster Pods */}
        <div className="grid grid-cols-2 gap-2 mt-0.5">
          <div
            className={`p-1.5 rounded text-center text-[10px] font-bold border transition-colors ${
              p.rcs_left > 0
                ? 'bg-cyan-950/80 border-cyan-400 text-cyan-300 shadow-[0_0_10px_rgba(0,240,255,0.4)]'
                : 'bg-slate-900 border-slate-800 text-slate-600'
            }`}
          >
            PORT RCS [LEFT] {p.rcs_left > 0 ? 'ACTIVE' : 'IDLE'}
          </div>
          <div
            className={`p-1.5 rounded text-center text-[10px] font-bold border transition-colors ${
              p.rcs_right > 0
                ? 'bg-cyan-950/80 border-cyan-400 text-cyan-300 shadow-[0_0_10px_rgba(0,240,255,0.4)]'
                : 'bg-slate-900 border-slate-800 text-slate-600'
            }`}
          >
            STBD RCS [RIGHT] {p.rcs_right > 0 ? 'ACTIVE' : 'IDLE'}
          </div>
        </div>
      </div>

      {/* Landing Gear Physical Contact Sensors */}
      <div className="bg-[#141B26] p-2.5 rounded border border-slate-800/80">
        <div className="text-slate-400 text-[10px] font-semibold mb-1.5 flex justify-between">
          <span>TOUCHDOWN CONTACT SENSORS</span>
          <span className={g.left_contact && g.right_contact ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
            {g.left_contact && g.right_contact ? 'DUAL LATCHED' : 'AIRBORNE'}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div
            className={`p-1.5 rounded text-center text-[10px] font-bold border transition-colors flex items-center justify-center gap-1.5 ${
              g.left_contact
                ? 'bg-emerald-950/90 border-emerald-400 text-emerald-300 shadow-[0_0_10px_rgba(0,230,118,0.5)]'
                : 'bg-slate-900 border-slate-800 text-slate-500'
            }`}
          >
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                g.left_contact ? 'bg-emerald-400 animate-ping' : 'bg-slate-700'
              }`}
            />
            LEFT GEAR: {g.left_contact ? 'CONTACT' : 'OPEN'}
          </div>

          <div
            className={`p-1.5 rounded text-center text-[10px] font-bold border transition-colors flex items-center justify-center gap-1.5 ${
              g.right_contact
                ? 'bg-emerald-950/90 border-emerald-400 text-emerald-300 shadow-[0_0_10px_rgba(0,230,118,0.5)]'
                : 'bg-slate-900 border-slate-800 text-slate-500'
            }`}
          >
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                g.right_contact ? 'bg-emerald-400 animate-ping' : 'bg-slate-700'
              }`}
            />
            RIGHT GEAR: {g.right_contact ? 'CONTACT' : 'OPEN'}
          </div>
        </div>
      </div>

      {/* Atmospheric Disturbances (if active) */}
      {(() => {
        const wind = typeof a?.wind_force === 'number' ? a.wind_force : (typeof (a as any)?.wind_x === 'number' ? (a as any).wind_x : 0);
        const turb = typeof a?.turbulence === 'number' ? a.turbulence : 0;
        return (Math.abs(wind) > 0.01 || Math.abs(turb) > 0.01) ? (
          <div className="bg-[#141B26] p-2 rounded border border-slate-800/80 text-[10px] flex justify-between text-slate-400">
            <span>WIND FORCE: <span className="text-amber-400 font-bold">{wind.toFixed(2)}</span></span>
            <span>TURBULENCE: <span className="text-amber-400 font-bold">{turb.toFixed(2)}</span></span>
          </div>
        ) : null;
      })()}
    </div>
  );
};
