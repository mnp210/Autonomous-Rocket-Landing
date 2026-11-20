import React from 'react';
import { PanelContainer } from '../common/PanelContainer';
import { StatusBadge } from '../common/StatusBadge';
import { DataGrid } from '../common/DataGrid';

export const ExperimentContextCard: React.FC = () => {
  const modelSpecs = [
    { label: 'Algorithm', value: 'PPO (Proximal Policy Optimization)', status: 'info' as const },
    { label: 'Policy Architecture', value: 'MlpPolicy [64, 64] tanh', status: 'muted' as const },
    { label: 'Framework', value: 'Stable-Baselines3 v2.3.2', status: 'muted' as const },
    { label: 'Active Checkpoint', value: 'Stage D Final (Seed 42)', status: 'nominal' as const },
    { label: 'Total Training Steps', value: '500,000 steps / run', status: 'muted' as const },
    { label: 'Study Sample Size', value: '12 Runs (4 Paradigms × 3 Seeds)', status: 'info' as const },
  ];

  const physicsSpecs = [
    { label: 'Physics Engine', value: 'Box2D (Gymnasium LunarLander-v3)', status: 'info' as const },
    { label: 'Server Timestep', value: '0.02 s (50 Hz authoritative)', status: 'nominal' as const },
    { label: 'Action Space', value: 'Discrete(4) [Coast, Left, Main, Right]', status: 'muted' as const },
    { label: 'Observation Space', value: 'Box(8) Continuous State Vector', status: 'muted' as const },
    { label: 'Gravity Range', value: '-7.5 to -15.0 m/s²', status: 'muted' as const },
    { label: 'Wind Simulation', value: 'Persistent Vector + Turbulence', status: 'muted' as const },
  ];

  const landingCriteria = [
    { label: 'Helipad Bounds (|x|)', value: '≤ 0.25 units', status: 'nominal' as const },
    { label: 'Lateral Velocity (|vx|)', value: '≤ 0.40 u/s', status: 'nominal' as const },
    { label: 'Descent Velocity (|vy|)', value: '≤ 0.40 u/s', status: 'nominal' as const },
    { label: 'Pitch Tilt (|θ|)', value: '≤ 0.20 rad (~11.5°)', status: 'nominal' as const },
    { label: 'Angular Rate (|dθ/dt|)', value: '≤ 0.35 rad/s', status: 'nominal' as const },
    { label: 'Landing Gear Contact', value: 'Both Legs Required', status: 'nominal' as const },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 font-mono">
      {/* 1. RL Model Architecture */}
      <PanelContainer
        title="MODEL ARCHITECTURE & WEIGHTS"
        subtitle="Stable-Baselines3 PPO Actor-Critic"
        badge={<StatusBadge label="VERIFIED" variant="nominal" size="sm" />}
      >
        <div className="space-y-3">
          <DataGrid items={modelSpecs} columns={1} />
          <div className="p-2 rounded bg-[#090D14] border border-slate-800 text-[10px] text-slate-400">
            <span className="text-cyan-400 font-bold">STATE ENCODING:</span> [pos_x, pos_y, vel_x, vel_y, angle, ang_vel, left_contact, right_contact]
          </div>
        </div>
      </PanelContainer>

      {/* 2. Authoritative Physics Engine */}
      <PanelContainer
        title="PHYSICS & SIMULATION SPECS"
        subtitle="Gymnasium Box2D Authoritative Backend"
        badge={<StatusBadge label="50 HZ" variant="info" size="sm" />}
      >
        <div className="space-y-3">
          <DataGrid items={physicsSpecs} columns={1} />
          <div className="p-2 rounded bg-[#090D14] border border-slate-800 text-[10px] text-slate-400">
            <span className="text-emerald-400 font-bold">COORDINATE MAPPING:</span> 1.0 Box2D unit = 10.0 meters. Pad surface at Y = 0.0 with footpad offset 1.083u.
          </div>
        </div>
      </PanelContainer>

      {/* 3. Strict Physical Landing Criteria */}
      <PanelContainer
        title="TOUCHDOWN ACCEPTANCE CRITERIA"
        subtitle="Enforced Physical Thresholds (benchmark_config.yaml)"
        badge={<StatusBadge label="STRICT" variant="warning" size="sm" />}
      >
        <div className="space-y-3">
          <DataGrid items={landingCriteria} columns={1} />
          <div className="p-2 rounded bg-[#090D14] border border-slate-800 text-[10px] text-slate-400">
            <span className="text-amber-400 font-bold">NOTE:</span> Crash/Success classification is derived directly from physical state transitions and Box2D collision events, never from cumulative reward alone.
          </div>
        </div>
      </PanelContainer>
    </div>
  );
};
