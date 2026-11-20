import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
import { TabNavigation } from '../components/common/TabNavigation';
import { StatusBadge } from '../components/common/StatusBadge';
import { TelemetryReadout } from '../components/common/TelemetryReadout';
import { PanelContainer } from '../components/common/PanelContainer';
import { StateVectorDisplay } from '../components/common/StateVectorDisplay';
import { EmptyState } from '../components/common/EmptyState';
import { BenchmarkMatrix } from '../components/dashboard/BenchmarkMatrix';
import { ExperimentContextCard } from '../components/dashboard/ExperimentContextCard';

describe('Aerospace Dashboard Primitives & Architecture', () => {
  let container: HTMLDivElement;
  let root: Root;

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

  it('TelemetryReadout renders values with tabular formatting and semantic classes', () => {
    act(() => {
      root.render(
        <TelemetryReadout
          label="ALTITUDE"
          value="12.45"
          unit="m"
          status="nominal"
          subtext="NOMINAL"
          auxLabel="TARGET"
          auxValue="0.00"
        />
      );
    });

    expect(container.textContent).toContain('ALTITUDE');
    expect(container.textContent).toContain('12.45');
    expect(container.textContent).toContain('m');
    expect(container.textContent).toContain('NOMINAL');
    expect(container.textContent).toContain('TARGET: 0.00');

    const valueSpan = container.querySelector('.text-emerald-400');
    expect(valueSpan).not.toBeNull();
    expect(valueSpan?.textContent).toBe('12.45');

    // Rerender with critical status
    act(() => {
      root.render(
        <TelemetryReadout
          label="SINK RATE"
          value="-2.85"
          unit="m/s"
          status="critical"
          subtext="EXCESSIVE"
        />
      );
    });

    const critSpan = container.querySelector('.text-rose-400');
    expect(critSpan).not.toBeNull();
    expect(critSpan?.textContent).toBe('-2.85');
    expect(container.textContent).toContain('EXCESSIVE');
  });

  it('StatusBadge renders variants with appropriate aerospace tokens', () => {
    act(() => {
      root.render(
        <StatusBadge label="CONFIRMED" variant="nominal" showDot dotPulse />
      );
    });

    expect(container.textContent).toContain('CONFIRMED');
    const badge = container.querySelector('span.text-emerald-400');
    expect(badge).not.toBeNull();

    act(() => {
      root.render(<StatusBadge label="WARNING" variant="warning" />);
    });
    expect(container.querySelector('span.text-amber-400')).not.toBeNull();

    act(() => {
      root.render(<StatusBadge label="FAULT" variant="critical" />);
    });
    expect(container.querySelector('span.text-rose-400')).not.toBeNull();
  });

  it('PanelContainer provides aerospace title bar, badges, and action slots', () => {
    act(() => {
      root.render(
        <PanelContainer
          title="SYSTEM METRICS"
          subtitle="Live Box2D Feed"
          badge={<StatusBadge label="50 HZ" variant="info" />}
          actionSlot={<button type="button" id="config-btn">CONFIG</button>}
        >
          <div id="panel-content">Active Telemetry Content</div>
        </PanelContainer>
      );
    });

    expect(container.textContent).toContain('SYSTEM METRICS');
    expect(container.textContent).toContain('Live Box2D Feed');
    expect(container.textContent).toContain('50 HZ');
    expect(container.querySelector('#config-btn')).not.toBeNull();
    expect(container.querySelector('#panel-content')?.textContent).toBe(
      'Active Telemetry Content'
    );
  });

  it('TabNavigation enforces ARIA accessibility and keyboard navigation', () => {
    const handleChange = vi.fn();
    const tabs = [
      { id: 'ops', label: 'OPERATIONS' },
      { id: 'research', label: 'RESEARCH' },
      { id: 'logs', label: 'LOGS' },
    ];

    act(() => {
      root.render(
        <TabNavigation
          tabs={tabs}
          activeTab="ops"
          onChange={handleChange}
          ariaLabel="Workspace Tabs"
        />
      );
    });

    const tablist = container.querySelector('[role="tablist"]');
    expect(tablist).not.toBeNull();
    expect(tablist?.getAttribute('aria-label')).toBe('Workspace Tabs');

    const tabButtons = container.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    expect(tabButtons.length).toBe(3);
    expect(tabButtons[0].getAttribute('aria-selected')).toBe('true');
    expect(tabButtons[0].tabIndex).toBe(0);
    expect(tabButtons[1].getAttribute('aria-selected')).toBe('false');
    expect(tabButtons[1].tabIndex).toBe(-1);

    // Arrow navigation: Right arrow
    act(() => {
      tabButtons[0].dispatchEvent(
        new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })
      );
    });
    expect(handleChange).toHaveBeenCalledWith('research');

    // Arrow navigation: Left arrow wraps around to last tab
    act(() => {
      tabButtons[0].dispatchEvent(
        new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true })
      );
    });
    expect(handleChange).toHaveBeenCalledWith('logs');

    // End key
    act(() => {
      tabButtons[0].dispatchEvent(
        new KeyboardEvent('keydown', { key: 'End', bubbles: true })
      );
    });
    expect(handleChange).toHaveBeenCalledWith('logs');

    // Home key
    act(() => {
      tabButtons[1].dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Home', bubbles: true })
      );
    });
    expect(handleChange).toHaveBeenCalledWith('ops');
  });

  it('StateVectorDisplay formats 2D and 3D coordinates accurately', () => {
    act(() => {
      root.render(
        <StateVectorDisplay
          label="POSITION VECTOR"
          vector={{ x: 0.125, y: -1.45 }}
          units="m"
          coordinateSystem="BOX2D LOCAL"
          precision={2}
        />
      );
    });

    expect(container.textContent).toContain('POSITION VECTOR');
    expect(container.textContent).toContain('BOX2D LOCAL');
    expect(container.textContent).toContain('+0.13');
    expect(container.textContent).toContain('-1.45');

    // 3D vector with Z component
    act(() => {
      root.render(
        <StateVectorDisplay
          label="VELOCITY VECTOR"
          vector={{ x: 0.0, y: -0.32, z: 0.0 }}
          units="m/s"
          coordinateSystem="3D WORLD"
          precision={2}
        />
      );
    });

    expect(container.textContent).toContain('Z');
    expect(container.textContent).toContain('+0.00');
  });

  it('EmptyState renders disciplined aerospace placeholder without visual clutter', () => {
    act(() => {
      root.render(
        <EmptyState
          title="AWAITING TRAJECTORY LOGS"
          description="Episode telemetry will record when simulation executes."
          statusLabel="STANDBY"
        />
      );
    });

    expect(container.textContent).toContain('AWAITING TRAJECTORY LOGS');
    expect(container.textContent).toContain('STANDBY');
    expect(container.textContent).toContain(
      'Episode telemetry will record when simulation executes.'
    );
  });
});

describe('Research Dashboard & Verified Benchmark Data Fidelity', () => {
  let container: HTMLDivElement;
  let root: Root;

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

  it('BenchmarkMatrix renders verified empirical figures from docs/benchmark_results.md', () => {
    act(() => {
      root.render(<BenchmarkMatrix />);
    });

    // Paradigm D figures
    expect(container.textContent).toContain('D: Curriculum + DR');
    expect(container.textContent).toContain('62.0%'); // Nominal success
    expect(container.textContent).toContain('38.8%'); // ID mean success
    expect(container.textContent).toContain('0.58° (0.0101 rad)'); // Resting tilt

    // Paradigm A (Standard baseline)
    expect(container.textContent).toContain('A: Standard PPO');
    expect(container.textContent).toContain('54.7%');

    // Paradigm B caveat (N=1)
    expect(container.textContent).toContain('B: DR Only (Uncurriculated)');
    expect(container.textContent).toContain('0.3%');
    expect(container.textContent).toContain('N = 1 (Caveat)*');

    // Environmental conditions
    expect(container.textContent).toContain('Standard_Nominal');
    expect(container.textContent).toContain('OOD_Extreme_Combined');
  });

  it('ExperimentContextCard presents accurate PPO and Box2D specifications', () => {
    act(() => {
      root.render(<ExperimentContextCard />);
    });

    expect(container.textContent).toContain('MODEL ARCHITECTURE & WEIGHTS');
    expect(container.textContent).toContain('PHYSICS & SIMULATION SPECS');
    expect(container.textContent).toContain('TOUCHDOWN ACCEPTANCE CRITERIA');

    // Specifications
    expect(container.textContent).toContain('PPO (Proximal Policy Optimization)');
    expect(container.textContent).toContain('MlpPolicy [64, 64] tanh');
    expect(container.textContent).toContain('0.02 s (50 Hz authoritative)');
    expect(container.textContent).toContain('Both Legs Required');
  });
});
