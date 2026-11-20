/**
 * Typed WebSocket Client Manager for Autonomous Rocket Landing simulation streaming.
 * Handles handshake, reconnection, heartbeats, and strict message routing.
 */

import type {
  ClientInitMessage,
  ClientInputMessage,
  ClientControlMessage,
  ClientPingMessage,
  ControlAckPayload,
  EpisodeCompletePayload,
  ErrorPayload,
  InputActionPayload,
  ServerWebSocketMessage,
  SessionInitPayload,
  SessionReadyPayload,
  SimulationSnapshotPayload,
} from '../types/protocol';

export type ConnectionStatus =
  | 'DISCONNECTED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'ERROR';

export interface WebSocketClientCallbacks {
  onStatusChange?: (status: ConnectionStatus) => void;
  onSessionReady?: (ready: SessionReadyPayload) => void;
  onSnapshot?: (snapshot: SimulationSnapshotPayload) => void;
  onEpisodeComplete?: (complete: EpisodeCompletePayload) => void;
  onControlAck?: (ack: ControlAckPayload) => void;
  onError?: (error: ErrorPayload) => void;
  onLatency?: (latencyMs: number) => void;
  onSessionExpired?: () => void;
  onSessionTakeover?: (message: string) => void;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private callbacks: WebSocketClientCallbacks;
  private status: ConnectionStatus = 'DISCONNECTED';

  // Session state
  private activeSessionId: string | null = null;
  private lastInitPayload: SessionInitPayload | null = null;

  // Heartbeat & Latency probe
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private pingTimestamp: number = 0;
  private latencyMs: number = 0;

  // Reconnection management
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private intentionalClose: boolean = false;

  constructor(url: string, callbacks: WebSocketClientCallbacks = {}) {
    this.url = url;
    this.callbacks = callbacks;
  }

  public get currentStatus(): ConnectionStatus {
    return this.status;
  }

  public get currentLatency(): number {
    return this.latencyMs;
  }

  public get sessionId(): string | null {
    return this.activeSessionId;
  }

  /**
   * Connects to the simulation WebSocket endpoint.
   */
  public connect(initPayload?: SessionInitPayload): void {
    if (initPayload) {
      this.lastInitPayload = initPayload;
      if (initPayload.session_id) {
        this.activeSessionId = initPayload.session_id;
      }
    }

    this.intentionalClose = false;
    this.setStatus(this.reconnectAttempts > 0 ? 'RECONNECTING' : 'CONNECTING');

    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      this.setStatus('ERROR');
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnects the socket cleanly and cancels pending reconnects.
   */
  public disconnect(): void {
    this.intentionalClose = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('DISCONNECTED');
  }

  /**
   * Sends SESSION_INIT to initialize or reconnect to a simulation session.
   */
  public initSession(payload: SessionInitPayload): void {
    this.lastInitPayload = payload;
    const msg: ClientInitMessage = {
      type: 'SESSION_INIT',
      payload,
    };
    this.send(msg);
  }

  /**
   * Sends manual pilot input action (0-3) with strict sequencing.
   */
  public sendAction(step: number, action: 0 | 1 | 2 | 3): void {
    const payload: InputActionPayload = {
      step,
      action,
      client_timestamp: performance.now() / 1000.0,
    };
    const msg: ClientInputMessage = {
      type: 'INPUT_ACTION',
      payload,
    };
    this.send(msg);
  }

  /**
   * Sends simulation flow control command (pause, resume, reset, set_speed).
   */
  public sendControl(command: 'pause' | 'resume' | 'reset' | 'set_speed', value?: number | null): void {
    const msg: ClientControlMessage = {
      type: 'CONTROL_CMD',
      payload: {
        command,
        value: value !== undefined ? value : null,
      },
    };
    this.send(msg);
  }

  // ===========================================================================
  // Internal Event Handlers
  // ===========================================================================

  private handleOpen(): void {
    this.reconnectAttempts = 0;
    this.setStatus('CONNECTED');
    this.startHeartbeat();

    // Automatically send initial handshake if configured
    if (this.lastInitPayload) {
      // Reconnection attempt retains active session ID if available
      const payload: SessionInitPayload = {
        ...this.lastInitPayload,
        session_id: this.activeSessionId,
      };
      this.initSession(payload);
    }
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data: ServerWebSocketMessage = JSON.parse(event.data);
      this.routeServerMessage(data);
    } catch (err) {
      console.error('Failed to parse incoming WebSocket frame:', err, event.data);
    }
  }

  private routeServerMessage(msg: ServerWebSocketMessage): void {
    switch (msg.type) {
      case 'SESSION_READY':
        this.activeSessionId = msg.payload.session_id;
        this.callbacks.onSessionReady?.(msg.payload);
        break;

      case 'SIMULATION_STEP':
        this.callbacks.onSnapshot?.(msg.payload);
        break;

      case 'EPISODE_COMPLETE':
        this.callbacks.onEpisodeComplete?.(msg.payload);
        break;

      case 'CONTROL_ACK':
        this.callbacks.onControlAck?.(msg.payload);
        break;

      case 'HEARTBEAT_PONG': {
        const now = performance.now();
        const rtt = Math.max(1, Math.round(now - this.pingTimestamp));
        this.latencyMs = rtt;
        this.callbacks.onLatency?.(rtt);
        break;
      }

      case 'ERROR':
        this.handleServerError(msg.payload);
        break;

      default:
        console.warn('Unhandled message type:', (msg as { type: string }).type);
        break;
    }
  }

  private handleServerError(error: ErrorPayload): void {
    console.warn(`Server error received [${error.code}]:`, error.message);
    this.callbacks.onError?.(error);

    if (error.code === 'SESSION_EXPIRED') {
      // Expired in-memory session: clear local session ID and notify for clean re-init
      this.activeSessionId = null;
      this.callbacks.onSessionExpired?.();
    } else if (error.code === 'SESSION_TAKEOVER') {
      // Evicted because another tab/connection claimed this session ID
      this.activeSessionId = null;
      this.callbacks.onSessionTakeover?.(error.message);
      this.disconnect();
    }
  }

  private handleError(event: Event): void {
    console.error('WebSocket connection error:', event);
    this.setStatus('ERROR');
  }

  private handleClose(): void {
    this.stopHeartbeat();
    if (!this.intentionalClose) {
      this.setStatus('DISCONNECTED');
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.intentionalClose) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('Max reconnect attempts reached. Stopping auto-reconnect.');
      this.setStatus('ERROR');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(5000, 1000 * Math.pow(1.5, this.reconnectAttempts - 1));
    this.setStatus('RECONNECTING');

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.pingTimestamp = performance.now();
        const pingMsg: ClientPingMessage = {
          type: 'HEARTBEAT_PING',
          payload: { timestamp: performance.now() / 1000.0 },
        };
        this.send(pingMsg);
      }
    }, 3000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private send(msg: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private setStatus(newStatus: ConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.callbacks.onStatusChange?.(newStatus);
    }
  }
}
