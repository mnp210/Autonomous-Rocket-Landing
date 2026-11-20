import React, { useState, useEffect } from 'react';
import { PanelContainer } from '../common/PanelContainer';
import { StatusBadge } from '../common/StatusBadge';
import { EmptyState } from '../common/EmptyState';
import { TrajectoryChart } from './charts/TrajectoryChart';
import { BrakingCorridorChart } from './charts/BrakingCorridorChart';
import { RewardChart } from './charts/RewardChart';
import { AttitudeChart } from './charts/AttitudeChart';
import {
  globalTelemetryStore,
  type TelemetryPoint,
  type CompletedEpisodeRecord,
} from '../../services/telemetryStore';

export const AnalyticsShell: React.FC = () => {
  const [points, setPoints] = useState<TelemetryPoint[]>(
    globalTelemetryStore.getActivePoints()
  );
  const [completedEpisodes, setCompletedEpisodes] = useState<CompletedEpisodeRecord[]>(
    globalTelemetryStore.getCompletedEpisodes()
  );
  const [isPaused, setIsPaused] = useState<boolean>(
    globalTelemetryStore.isChartsPaused()
  );

  useEffect(() => {
    const unsubscribe = globalTelemetryStore.subscribe(() => {
      setPoints([...globalTelemetryStore.getActivePoints()]);
      setCompletedEpisodes([...globalTelemetryStore.getCompletedEpisodes()]);
    });
    return unsubscribe;
  }, []);

  const handleTogglePause = () => {
    const next = !isPaused;
    setIsPaused(next);
    globalTelemetryStore.setChartsPaused(next);
  };

  const handleClearTrails = () => {
    globalTelemetryStore.resetActiveEpisode();
  };

  const hasPoints = points.length > 0;

  return (
    <div className="space-y-4 font-mono text-xs">
      {/* Chart Control Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-[#0D1117] border border-slate-800/80">
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                hasPoints
                  ? isPaused
                    ? 'bg-amber-400'
                    : 'bg-emerald-400 animate-pulse'
                  : 'bg-slate-500'
              }`}
            />
            LIVE FLIGHT DYNAMICS & TELEMETRY CHARTS
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-[10px] text-slate-400 tabular-nums">
            ACTIVE SAMPLES: <strong className="text-cyan-300">{points.length}</strong> (50 Hz)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleTogglePause}
            className={`px-2.5 py-1 rounded text-[10px] font-bold border transition-colors ${
              isPaused
                ? 'bg-amber-950/80 border-amber-500 text-amber-300'
                : 'bg-slate-900 border-slate-700 text-slate-300 hover:text-white'
            }`}
          >
            {isPaused ? '▶ RESUME VISUAL UPDATES' : '⏸ PAUSE VISUAL UPDATES'}
          </button>

          <button
            type="button"
            onClick={handleClearTrails}
            className="px-2.5 py-1 rounded text-[10px] font-bold border bg-slate-900 border-slate-700 text-slate-300 hover:text-rose-300 hover:border-rose-500 transition-colors"
          >
            ↺ RESET CHART TRAILS
          </button>
        </div>
      </div>

      {/* Flight Dynamics & Trajectory Profiles */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* 1. Trajectory Trace Y(X) */}
        <PanelContainer
          title="DESCENT TRAJECTORY PROFILE"
          subtitle="Altitude Y vs Lateral Displacement X (Box2D World Units)"
          badge={
            <StatusBadge
              label={hasPoints ? 'LIVE TRACE' : 'STANDBY'}
              variant={hasPoints ? 'info' : 'neutral'}
              size="sm"
            />
          }
        >
          {hasPoints ? (
            <div className="h-64 flex flex-col justify-between p-1 bg-[#090D14] border border-slate-800/80 rounded">
              <TrajectoryChart points={points} />
            </div>
          ) : (
            <div className="h-64 flex flex-col justify-between p-2 bg-[#090D14] border border-slate-800/80 rounded">
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>Y-Axis: Altitude (0.0 to 1.8u)</span>
                <span>Pad Target: X = 0.0u</span>
              </div>
              <EmptyState
                title="AWAITING FLIGHT TRAJECTORY DATA"
                description="Coordinate trace will render when an active simulation episode executes. Trajectory points sample at 50 Hz from authoritative Box2D state."
                statusLabel="STANDBY"
                className="border-none bg-transparent"
              />
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>X-Axis: Lateral Offset (-2.5 to +2.5u)</span>
                <span>1.0u = Box2D unit</span>
              </div>
            </div>
          )}
        </PanelContainer>

        {/* 2. Vertical Sink Rate Profile vy(Y) */}
        <PanelContainer
          title="BRAKING CORRIDOR PROFILE"
          subtitle="Descent Velocity Vy vs Footpad Clearance Y (Box2D Units)"
          badge={
            <StatusBadge
              label={hasPoints ? 'LIVE TRACE' : 'STANDBY'}
              variant={hasPoints ? 'nominal' : 'neutral'}
              size="sm"
            />
          }
        >
          {hasPoints ? (
            <div className="h-64 flex flex-col justify-between p-1 bg-[#090D14] border border-slate-800/80 rounded">
              <BrakingCorridorChart points={points} />
            </div>
          ) : (
            <div className="h-64 flex flex-col justify-between p-2 bg-[#090D14] border border-slate-800/80 rounded">
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>Y-Axis: Velocity Vy (-2.5 to +0.5 u/s)</span>
                <span>Limit: ≥ -0.40 u/s</span>
              </div>
              <EmptyState
                title="AWAITING DESCENT VELOCITY LOGS"
                description="Braking curve and terminal throttle schedule will plot against physical landing limits as flight progresses."
                statusLabel="STANDBY"
                className="border-none bg-transparent"
              />
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>X-Axis: Altitude (0.0 to 1.8u)</span>
                <span>Touchdown: 0.0u</span>
              </div>
            </div>
          )}
        </PanelContainer>
      </div>

      {/* Control Effort & Reward Progression */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* 3. Cumulative Reward Curve */}
        <PanelContainer
          title="CUMULATIVE RETURN PROGRESSION"
          subtitle="Cumulative Reward R(t) vs Simulation Time (Seconds)"
          badge={
            <StatusBadge
              label={hasPoints ? 'LIVE TRACE' : 'STANDBY'}
              variant={hasPoints ? 'info' : 'neutral'}
              size="sm"
            />
          }
        >
          {hasPoints ? (
            <div className="h-64 flex flex-col justify-between p-1 bg-[#090D14] border border-slate-800/80 rounded">
              <RewardChart points={points} />
            </div>
          ) : (
            <div className="h-64 flex flex-col justify-between p-2 bg-[#090D14] border border-slate-800/80 rounded">
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>Reward Range (-100 to +300)</span>
                <span>Target: &gt; +200</span>
              </div>
              <EmptyState
                title="AWAITING REWARD TELEMETRY"
                description="Step-wise shaped reward and terminal touchdown payoff curves will render upon flight execution."
                statusLabel="STANDBY"
                className="border-none bg-transparent"
              />
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>Simulation Time (Seconds, 50 Hz)</span>
                <span>Max Horizon: 1000 Steps</span>
              </div>
            </div>
          )}
        </PanelContainer>

        {/* 4. Attitude & Angular Rate */}
        <PanelContainer
          title="ATTITUDE STABILIZATION PROFILE"
          subtitle="Pitch Angle θ (deg/rad) vs Time (Strict Limits ±0.20 rad)"
          badge={
            <StatusBadge
              label={hasPoints ? 'LIVE TRACE' : 'STANDBY'}
              variant={hasPoints ? 'warning' : 'neutral'}
              size="sm"
            />
          }
        >
          {hasPoints ? (
            <div className="h-64 flex flex-col justify-between p-1 bg-[#090D14] border border-slate-800/80 rounded">
              <AttitudeChart points={points} />
            </div>
          ) : (
            <div className="h-64 flex flex-col justify-between p-2 bg-[#090D14] border border-slate-800/80 rounded">
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>Pitch Limit: ±0.20 rad (±11.5°)</span>
                <span>Spin Limit: ±0.35 rad/s</span>
              </div>
              <EmptyState
                title="AWAITING ATTITUDE GYROSCOPE LOGS"
                description="Real-time orientation and RCS counter-torque responses will map continuously during flight."
                statusLabel="STANDBY"
                className="border-none bg-transparent"
              />
              <div className="flex justify-between text-[10px] text-slate-500 uppercase">
                <span>Simulation Time (Seconds, 50 Hz)</span>
                <span>Upright Rest: θ = 0.0°</span>
              </div>
            </div>
          )}
        </PanelContainer>
      </div>

      {/* 5. Live Episode Log Table */}
      <PanelContainer
        title="SESSION EPISODE HISTORY & TELEMETRY LOG"
        subtitle="Chronological Record of Completed Simulation Episodes in Active Session"
        badge={
          <StatusBadge
            label={`${completedEpisodes.length} EPISODES RECORDED`}
            variant={completedEpisodes.length > 0 ? 'nominal' : 'neutral'}
            size="sm"
          />
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#101622] text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <th className="py-2 px-3">Episode #</th>
                <th className="py-2 px-3">Mode</th>
                <th className="py-2 px-3 text-right">Steps</th>
                <th className="py-2 px-3 text-right">Sim Time</th>
                <th className="py-2 px-3 text-right">Final Clearance</th>
                <th className="py-2 px-3 text-right">Impact Vy</th>
                <th className="py-2 px-3 text-right">Final Tilt</th>
                <th className="py-2 px-3 text-right">Cumulative Reward</th>
                <th className="py-2 px-3 text-center">Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 tabular-nums">
              {completedEpisodes.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center">
                      <span className="text-slate-400 font-bold mb-1">
                        NO EPISODES RECORDED IN ACTIVE SESSION
                      </span>
                      <span className="text-[11px] text-slate-500 max-w-md">
                        Execute flights in Live Operations. Completed episodes will automatically record into this table with verified landing metrics and Box2D physics outcomes.
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                completedEpisodes.map((ep) => (
                  <tr key={ep.episode_id} className="hover:bg-[#141B26] transition-colors">
                    <td className="py-2.5 px-3 font-bold text-slate-200">
                      EP #{ep.episode_id}
                    </td>
                    <td className="py-2.5 px-3 uppercase text-slate-400 text-[10px]">
                      {ep.mode}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {ep.total_steps}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {ep.total_sim_time.toFixed(2)}s
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {ep.final_clearance.toFixed(3)}u
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {ep.impact_vel_y !== null && ep.impact_vel_y !== undefined
                        ? `${ep.impact_vel_y.toFixed(2)} u/s`
                        : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {ep.impact_tilt_deg !== null && ep.impact_tilt_deg !== undefined
                        ? `${ep.impact_tilt_deg.toFixed(1)}°`
                        : '—'}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-bold ${
                        ep.cumulative_reward >= 200
                          ? 'text-emerald-400'
                          : ep.cumulative_reward >= 0
                          ? 'text-cyan-300'
                          : 'text-rose-400'
                      }`}
                    >
                      {ep.cumulative_reward >= 0
                        ? `+${ep.cumulative_reward.toFixed(1)}`
                        : ep.cumulative_reward.toFixed(1)}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[9px] font-bold tracking-wider ${
                          ep.outcome === 'SUCCESS'
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/40'
                            : ep.outcome === 'CRASH'
                            ? 'bg-rose-950 text-rose-400 border border-rose-500/40'
                            : 'bg-amber-950 text-amber-400 border border-amber-500/40'
                        }`}
                      >
                        {ep.outcome}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </PanelContainer>
    </div>
  );
};
