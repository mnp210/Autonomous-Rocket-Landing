import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

import { DashboardShell } from '../components/dashboard/DashboardShell';
import { LiveOperationsView } from '../components/dashboard/LiveOperationsView';
import type { SimulationSnapshotPayload, SessionReadyPayload } from '../types/protocol';

describe('Stage 9.4.4 Dashboard Full Integration & Acceptance Tests', () => {
  let container: HTMLDivElement;
  let root: Root;

  const mockSnapshot: SimulationSnapshotPayload = {
    protocol_version: '2.0',
    session_id: 'test-session-integration',
    episode_id: 1,
    kinematics: {
      pos_x: 0.12,
      pos_y: 5.60,
      vel_x: -0.05,
      vel_y: -0.32,
      angle: 0.02,
      ang_vel: 0.01,
      altitude: 4.52,
    },
    propulsion: {
      action: 2,
      throttle: 0.85,
      rcs_left: 0.0,
      rcs_right: 0.2,
    },
    landing_gear: {
      left_contact: false,
      right_contact: false,
    },
    atmosphere: {
      wind_force: 2.5,
      turbulence: 0.4,
    },
    lifecycle: {
      step: 142,
      sim_time: 2.84,
      touchdown_phase: 'AIRBORNE',
      step_reward: 12.4,
      cumulative_reward: 184.2,
      terminated: false,
      truncated: false,
    },
    impact: {},
  };

  const mockSessionReady: SessionReadyPayload = {
    session_id: 'test-session-integration',
    dt: 0.02,
    mode: 'ai',
    policy_mode: 'deterministic',
    seed: 42,
    helipad_bounds: [-1.5, 1.5, 0.0],
    terrain: [
      [-10, 0],
      [-1.5, 0],
      [1.5, 0],
      [10, 0],
    ],
  };

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  describe('Unified Navigation & View Switching', () => {
    it('renders DashboardShell with MissionHeader, status indicators, and defaults to Live Operations', () => {
      act(() => {
        root.render(
          <DashboardShell
            connectionStatus="CONNECTED"
            latencyMs={18}
            sessionId="test-session-integration"
            errorMessage={null}
            onClearError={vi.fn()}
            onReconnect={vi.fn()}
            viewMode="2d"
            onViewModeChange={vi.fn()}
            flightMode="ai"
            policyMode="deterministic"
            isPaused={false}
            speedFactor={1.0}
            currentStep={142}
            sessionReady={mockSessionReady}
            latestSnapshot={mockSnapshot}
            interpolatedSnapshot={mockSnapshot}
            episodeComplete={null}
            showDebrief={false}
            onCloseDebrief={vi.fn()}
            onReopenDebrief={vi.fn()}
            onResetEpisode={vi.fn()}
            onModeChange={vi.fn()}
            onControlCmd={vi.fn()}
            onSendAction={vi.fn()}
          />
        );
      });

      // Branding & Status
      expect(container.textContent).toContain('AUTONOMOUS ROCKET LANDING');
      expect(container.textContent).toContain('STAGE 9.4 // RESEARCH & OPS');
      expect(container.textContent).toContain('LIVE OPERATIONS');
      expect(container.textContent).toContain('RESEARCH & BENCHMARKS');
      expect(container.textContent).toContain('CONNECTED');
      expect(container.textContent).toContain('18ms');

      // Live Operations is default active view
      expect(container.textContent).toContain('VIEWPORT MODE:');
      expect(container.textContent).toContain('2D ENGINEERING CANVAS');
      expect(container.textContent).toContain('PRIMARY FLIGHT TELEMETRY');
      expect(container.textContent).toContain('FLIGHT CONTROL REGIME');
    });

    it('switches between Live Operations and Research Dashboard without unmounting root shell', () => {
      act(() => {
        root.render(
          <DashboardShell
            connectionStatus="CONNECTED"
            latencyMs={18}
            sessionId="test-session-integration"
            errorMessage={null}
            onClearError={vi.fn()}
            onReconnect={vi.fn()}
            viewMode="2d"
            onViewModeChange={vi.fn()}
            flightMode="ai"
            policyMode="deterministic"
            isPaused={false}
            speedFactor={1.0}
            currentStep={142}
            sessionReady={mockSessionReady}
            latestSnapshot={mockSnapshot}
            interpolatedSnapshot={mockSnapshot}
            episodeComplete={null}
            showDebrief={false}
            onCloseDebrief={vi.fn()}
            onReopenDebrief={vi.fn()}
            onResetEpisode={vi.fn()}
            onModeChange={vi.fn()}
            onControlCmd={vi.fn()}
            onSendAction={vi.fn()}
          />
        );
      });

      // Switch to Research & Benchmarks
      const researchTabBtn = Array.from(container.querySelectorAll('button')).find(
        (b) => b.textContent?.includes('RESEARCH & BENCHMARKS')
      );
      expect(researchTabBtn).toBeDefined();

      act(() => {
        researchTabBtn?.click();
      });

      // Research Dashboard view rendered
      expect(container.textContent).toContain('AI RESEARCH & EXPERIMENT WORKSTATION');
      expect(container.textContent).toContain('PARADIGM MATRIX');
      expect(container.textContent).toContain('OUTCOMES & FAILURES');
      expect(container.textContent).toContain('ENVIRONMENTAL STRESS');
      expect(container.textContent).toContain('PROVENANCE & STATS');
      expect(container.textContent).toContain('FLIGHT DYNAMICS');
      expect(container.textContent).toContain('SYSTEM SPECS');

      // Switch back to Live Operations
      const opsTabBtn = Array.from(container.querySelectorAll('button')).find(
        (b) => b.textContent?.includes('LIVE OPERATIONS')
      );
      expect(opsTabBtn).toBeDefined();

      act(() => {
        opsTabBtn?.click();
      });

      expect(container.textContent).toContain('PRIMARY FLIGHT TELEMETRY');
      expect(container.textContent).toContain('2D ENGINEERING CANVAS');
    });

    it('preserves active research subtab across view switches', () => {
      act(() => {
        root.render(
          <DashboardShell
            connectionStatus="CONNECTED"
            latencyMs={18}
            sessionId="test-session-integration"
            errorMessage={null}
            onClearError={vi.fn()}
            onReconnect={vi.fn()}
            viewMode="2d"
            onViewModeChange={vi.fn()}
            flightMode="ai"
            policyMode="deterministic"
            isPaused={false}
            speedFactor={1.0}
            currentStep={142}
            sessionReady={mockSessionReady}
            latestSnapshot={mockSnapshot}
            interpolatedSnapshot={mockSnapshot}
            episodeComplete={null}
            showDebrief={false}
            onCloseDebrief={vi.fn()}
            onReopenDebrief={vi.fn()}
            onResetEpisode={vi.fn()}
            onModeChange={vi.fn()}
            onControlCmd={vi.fn()}
            onSendAction={vi.fn()}
          />
        );
      });

      // Navigate to Research
      const researchTabBtn = Array.from(container.querySelectorAll('button')).find(
        (b) => b.textContent?.includes('RESEARCH & BENCHMARKS')
      );
      act(() => {
        researchTabBtn?.click();
      });

      // Switch subtab to ENVIRONMENTAL STRESS
      const stressSubTabBtn = Array.from(container.querySelectorAll('button')).find(
        (b) => b.textContent?.includes('ENVIRONMENTAL STRESS')
      );
      expect(stressSubTabBtn).toBeDefined();

      act(() => {
        stressSubTabBtn?.click();
      });

      expect(container.textContent).toContain('DISTRIBUTIONAL ROBUSTNESS EVALUATION');

      // Navigate back to Live Operations
      const opsTabBtn = Array.from(container.querySelectorAll('button')).find(
        (b) => b.textContent?.includes('LIVE OPERATIONS')
      );
      act(() => {
        opsTabBtn?.click();
      });

      // Navigate back to Research: should still be on ENVIRONMENTAL STRESS
      act(() => {
        researchTabBtn?.click();
      });

      expect(container.textContent).toContain('DISTRIBUTIONAL ROBUSTNESS EVALUATION');
    });

    it('LiveOperationsView provides direct shortcut button to FLIGHT CHARTS (4)', () => {
      const handleNavigateToResearch = vi.fn();

      act(() => {
        root.render(
          <LiveOperationsView
            viewMode="2d"
            onViewModeChange={vi.fn()}
            interpolatedSnapshot={mockSnapshot}
            latestSnapshot={mockSnapshot}
            sessionReady={mockSessionReady}
            flightMode="ai"
            policyMode="deterministic"
            isPaused={false}
            speedFactor={1.0}
            currentStep={142}
            latencyMs={18}
            hasDebrief={false}
            onReopenDebrief={vi.fn()}
            onModeChange={vi.fn()}
            onControlCmd={vi.fn()}
            onSendAction={vi.fn()}
            onNavigateToResearch={handleNavigateToResearch}
          />
        );
      });

      const chartsBtn = Array.from(container.querySelectorAll('button')).find(
        (b) => b.textContent?.includes('FLIGHT CHARTS (4)')
      );
      expect(chartsBtn).toBeDefined();

      act(() => {
        chartsBtn?.click();
      });

      expect(handleNavigateToResearch).toHaveBeenCalledWith('analytics');
    });
  });

  describe('Telemetry Display & Honest Units Audit', () => {
    it('renders telemetry and benchmark data using strictly honest Box2D simulation units', () => {
      act(() => {
        root.render(
          <LiveOperationsView
            viewMode="2d"
            onViewModeChange={vi.fn()}
            interpolatedSnapshot={mockSnapshot}
            latestSnapshot={mockSnapshot}
            sessionReady={mockSessionReady}
            flightMode="ai"
            policyMode="deterministic"
            isPaused={false}
            speedFactor={1.0}
            currentStep={142}
            latencyMs={18}
            hasDebrief={false}
            onReopenDebrief={vi.fn()}
            onModeChange={vi.fn()}
            onControlCmd={vi.fn()}
            onSendAction={vi.fn()}
          />
        );
      });

      // Verify Telemetry Panel units
      expect(container.textContent).toContain('PAD CLEARANCE');
      expect(container.textContent).toContain('4.52 units');
      expect(container.textContent).toContain('VERT VELOCITY (Vy)');
      expect(container.textContent).toContain('-0.32 u/s');
      expect(container.textContent).toContain('HORIZ VELOCITY (Vx)');
      expect(container.textContent).toContain('-0.05 u/s');
    });
  });
});
