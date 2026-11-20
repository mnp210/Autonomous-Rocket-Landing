/**
 * Main Application Component for the Stage 9.4.1 Research & Engineering Dashboard.
 *
 * Coordinates WebSocket connection, client-side jitter buffer,
 * state hoisting, and delegates presentation to DashboardShell.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { DashboardShell } from './components/dashboard/DashboardShell';
import { JitterBuffer } from './services/jitterBuffer';
import { WebSocketClient, type ConnectionStatus } from './services/websocketClient';
import { globalTelemetryStore } from './services/telemetryStore';
import type {
  EpisodeCompletePayload,
  FlightMode,
  PolicyMode,
  SessionReadyPayload,
  SimulationSnapshotPayload,
} from './types/protocol';

export const App: React.FC = () => {
  // URL Query Parameters support for direct mode loading
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const initialMode: FlightMode = (urlParams?.get('mode') as FlightMode) || 'ai';
  const initialPolicy: PolicyMode = (urlParams?.get('policy') as PolicyMode) || 'deterministic';
  const initialView: '2d' | '3d' = urlParams?.get('view') === '3d' ? '3d' : '2d';

  // View Mode: 2D Engineering vs 3D Cinematic
  const [viewMode, setViewMode] = useState<'2d' | '3d'>(initialView);

  // Connection & Latency
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('DISCONNECTED');
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Simulation State
  const [sessionReady, setSessionReady] = useState<SessionReadyPayload | null>(null);
  const [latestSnapshot, setLatestSnapshot] = useState<SimulationSnapshotPayload | null>(null);
  const [episodeComplete, setEpisodeComplete] = useState<EpisodeCompletePayload | null>(
    urlParams?.get('debrief') === '1'
      ? {
          session_id: 'demo-completed-flight',
          episode_id: 1,
          outcome: 'SUCCESS',
          total_steps: 248,
          total_sim_time: 4.96,
          cumulative_reward: 264.8,
          impact_vel_x: 0.04,
          impact_vel_y: -0.32,
          impact_tilt_deg: 1.2,
          final_clearance: 0.0,
          final_tilt_deg: 0.4,
        }
      : null
  );
  const [showDebrief, setShowDebrief] = useState<boolean>(urlParams?.get('debrief') === '1');

  // Flight Mode & Controls
  const [flightMode, setFlightMode] = useState<FlightMode>(initialMode);
  const flightModeRef = useRef<FlightMode>(initialMode);
  useEffect(() => {
    flightModeRef.current = flightMode;
  }, [flightMode]);

  const [policyMode, setPolicyMode] = useState<PolicyMode>(initialPolicy);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [speedFactor, setSpeedFactor] = useState<number>(1.0);

  // System Notifications
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Jitter buffer and WebSocket client references
  const jitterBufferRef = useRef<JitterBuffer>(new JitterBuffer());
  const wsClientRef = useRef<WebSocketClient | null>(null);

  // Current interpolated snapshot for rendering
  const [interpolatedSnapshot, setInterpolatedSnapshot] = useState<SimulationSnapshotPayload | null>(null);

  // Resolve backend WebSocket endpoint URL
  const resolveWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // If running in Vite dev mode on 5173, point to backend on 8000
    const host =
      window.location.port === '5173'
        ? `${window.location.hostname}:8000`
        : window.location.host;
    return `${protocol}//${host}/ws/simulation`;
  }, []);

  // Initialize and connect WebSocket Client
  useEffect(() => {
    const wsUrl = resolveWsUrl();
    const jb = jitterBufferRef.current;

    const client = new WebSocketClient(wsUrl, {
      onStatusChange: (status) => {
        setConnectionStatus(status);
        if (status === 'CONNECTED') {
          setErrorMessage(null);
        }
      },
      onSessionReady: (ready) => {
        setSessionReady(ready);
        setSessionId(ready.session_id);
        jb.clear();
        globalTelemetryStore.resetActiveEpisode();
        if (urlParams?.get('debrief') !== '1') {
          setShowDebrief(false);
          setEpisodeComplete(null);
        }
      },
      onSnapshot: (snap) => {
        jb.push(snap);
        setLatestSnapshot(snap);
        globalTelemetryStore.pushSnapshot(snap, flightModeRef.current);

        // Check for episode completion directly from lifecycle
        if (snap.lifecycle.terminated || snap.lifecycle.truncated) {
          setShowDebrief(true);
        }
      },
      onEpisodeComplete: (complete) => {
        setEpisodeComplete(complete);
        setShowDebrief(true);
        globalTelemetryStore.pushEpisodeComplete(complete, flightModeRef.current);
      },
      onControlAck: (ack) => {
        if (ack.command === 'pause') setIsPaused(true);
        if (ack.command === 'resume') setIsPaused(false);
        if (ack.command === 'set_speed' && typeof ack.speed === 'number') {
          setSpeedFactor(ack.speed);
        }
        if (ack.command === 'reset') {
          setShowDebrief(false);
          setEpisodeComplete(null);
          jb.clear();
          globalTelemetryStore.resetActiveEpisode();
        }
      },
      onError: (err) => {
        setErrorMessage(`[${err.code}] ${err.message}`);
        // Auto-dismiss transient warnings after 6 seconds
        setTimeout(() => setErrorMessage(null), 6000);
      },
      onLatency: (rtt) => {
        setLatencyMs(rtt);
      },
      onSessionExpired: () => {
        // Re-initialize a clean session
        client.initSession({
          mode: flightMode,
          policy_mode: policyMode,
          seed: null,
        });
      },
      onSessionTakeover: (msg) => {
        setErrorMessage(`Session Displaced: ${msg}`);
      },
    });

    wsClientRef.current = client;

    // Initial connection handshake
    client.connect({
      mode: initialMode,
      policy_mode: initialPolicy,
      seed: 42,
    });

    return () => {
      client.disconnect();
      wsClientRef.current = null;
    };
  }, [resolveWsUrl]); // Run once on mount

  // Interpolation rendering ticker (60 FPS)
  useEffect(() => {
    let animId: number;
    const jb = jitterBufferRef.current;

    const tick = () => {
      const snap = jb.getInterpolatedSnapshot();
      if (snap) {
        setInterpolatedSnapshot(snap);
      }
      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, []);

  // Mode Change Handler
  const handleModeChange = useCallback((mode: FlightMode, policy: PolicyMode = 'deterministic') => {
    setFlightMode(mode);
    setPolicyMode(policy);
    setShowDebrief(false);
    setEpisodeComplete(null);

    if (wsClientRef.current) {
      wsClientRef.current.initSession({
        mode,
        policy_mode: policy,
        seed: null,
      });
    }
  }, []);

  // Control Command Dispatcher (Pause, Resume, Reset, Speed)
  const handleControlCmd = useCallback(
    (command: 'pause' | 'resume' | 'reset' | 'set_speed', value?: number | null) => {
      if (wsClientRef.current) {
        wsClientRef.current.sendControl(command, value);
      }
    },
    []
  );

  // Manual Action Dispatcher
  const handleSendAction = useCallback((step: number, action: 0 | 1 | 2 | 3) => {
    if (wsClientRef.current) {
      wsClientRef.current.sendAction(step, action);
    }
  }, []);

  // Reconnection Handler
  const handleReconnect = useCallback(() => {
    if (wsClientRef.current) {
      wsClientRef.current.connect({
        mode: flightMode,
        policy_mode: policyMode,
        seed: null,
      });
    }
  }, [flightMode, policyMode]);

  const currentStep = latestSnapshot ? latestSnapshot.lifecycle.step : 0;

  return (
    <DashboardShell
      connectionStatus={connectionStatus}
      latencyMs={latencyMs}
      sessionId={sessionId}
      errorMessage={errorMessage}
      onClearError={() => setErrorMessage(null)}
      onReconnect={handleReconnect}
      viewMode={viewMode}
      onViewModeChange={setViewMode}
      flightMode={flightMode}
      policyMode={policyMode}
      isPaused={isPaused}
      speedFactor={speedFactor}
      currentStep={currentStep}
      sessionReady={sessionReady}
      latestSnapshot={latestSnapshot}
      interpolatedSnapshot={interpolatedSnapshot}
      episodeComplete={episodeComplete}
      showDebrief={showDebrief}
      onCloseDebrief={() => setShowDebrief(false)}
      onReopenDebrief={() => setShowDebrief(true)}
      onResetEpisode={() => {
        setShowDebrief(false);
        setEpisodeComplete(null);
        handleControlCmd('reset');
      }}
      onModeChange={handleModeChange}
      onControlCmd={handleControlCmd}
      onSendAction={handleSendAction}
    />
  );
};

export default App;
