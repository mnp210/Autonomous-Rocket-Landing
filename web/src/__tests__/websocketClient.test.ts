import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketClient } from '../services/websocketClient';
import type { ServerWebSocketMessage } from '../types/protocol';

class MockWebSocket {
  public static OPEN = 1;
  public static CONNECTING = 0;
  public static CLOSING = 2;
  public static CLOSED = 3;

  public readyState: number = 1; // WebSocket.OPEN
  public sentData: string[] = [];
  public url: string;
  public onopen: (() => void) | null = null;
  public onmessage: ((e: { data: string }) => void) | null = null;
  public onerror: ((e: unknown) => void) | null = null;
  public onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 5);
  }

  send(data: string) {
    this.sentData.push(data);
  }

  close() {
    this.readyState = 3; // WebSocket.CLOSED
    if (this.onclose) this.onclose();
  }

  // Helper to simulate incoming server message
  simulateMessage(msg: ServerWebSocketMessage) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(msg) });
    }
  }
}

describe('WebSocketClient', () => {
  let originalWebSocket: typeof globalThis.WebSocket;

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket;
    (globalThis as unknown as { WebSocket: typeof MockWebSocket }).WebSocket = MockWebSocket;
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
    vi.restoreAllMocks();
  });

  it('connects and transitions status to CONNECTED', async () => {
    const onStatusChange = vi.fn();
    const client = new WebSocketClient('ws://localhost:8000/ws/simulation', {
      onStatusChange,
    });

    client.connect({ mode: 'ai', seed: 42 });

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(client.currentStatus).toBe('CONNECTED');
    expect(onStatusChange).toHaveBeenCalledWith('CONNECTED');

    client.disconnect();
    expect(client.currentStatus).toBe('DISCONNECTED');
  });

  it('routes SESSION_READY and updates active session ID', async () => {
    const onSessionReady = vi.fn();
    const client = new WebSocketClient('ws://localhost:8000/ws/simulation', {
      onSessionReady,
    });

    client.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    // Access mock socket
    const mockWs = (client as unknown as { ws: MockWebSocket }).ws;
    mockWs.simulateMessage({
      type: 'SESSION_READY',
      payload: {
        session_id: 'session-uuid-42',
        dt: 0.02,
        mode: 'ai',
        policy_mode: 'deterministic',
        seed: 42,
        helipad_bounds: [8.0, 12.0, 3.333],
        terrain: [[-10, 0], [10, 0]],
      },
    });

    expect(onSessionReady).toHaveBeenCalled();
    expect(client.sessionId).toBe('session-uuid-42');

    client.disconnect();
  });

  it('handles SESSION_EXPIRED by triggering onSessionExpired callback', async () => {
    const onSessionExpired = vi.fn();
    const onError = vi.fn();
    const client = new WebSocketClient('ws://localhost:8000/ws/simulation', {
      onSessionExpired,
      onError,
    });

    client.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    const mockWs = (client as unknown as { ws: MockWebSocket }).ws;
    mockWs.simulateMessage({
      type: 'ERROR',
      payload: {
        code: 'SESSION_EXPIRED',
        message: 'Session has expired',
      },
    });

    expect(onError).toHaveBeenCalledWith({
      code: 'SESSION_EXPIRED',
      message: 'Session has expired',
    });
    expect(onSessionExpired).toHaveBeenCalled();
    expect(client.sessionId).toBeNull();

    client.disconnect();
  });

  it('handles SESSION_TAKEOVER by disconnecting and triggering onSessionTakeover', async () => {
    const onSessionTakeover = vi.fn();
    const client = new WebSocketClient('ws://localhost:8000/ws/simulation', {
      onSessionTakeover,
    });

    client.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    const mockWs = (client as unknown as { ws: MockWebSocket }).ws;
    mockWs.simulateMessage({
      type: 'ERROR',
      payload: {
        code: 'SESSION_TAKEOVER',
        message: 'A new connection has claimed control of this session',
      },
    });

    expect(onSessionTakeover).toHaveBeenCalledWith(
      'A new connection has claimed control of this session'
    );
    expect(client.currentStatus).toBe('DISCONNECTED');
  });

  it('sends structured INPUT_ACTION and CONTROL_CMD messages', async () => {
    const client = new WebSocketClient('ws://localhost:8000/ws/simulation');
    client.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    const mockWs = (client as unknown as { ws: MockWebSocket }).ws;

    client.sendAction(5, 2);
    const sentAction = JSON.parse(mockWs.sentData[mockWs.sentData.length - 1]);
    expect(sentAction.type).toBe('INPUT_ACTION');
    expect(sentAction.payload.step).toBe(5);
    expect(sentAction.payload.action).toBe(2);

    client.sendControl('pause');
    const sentCtrl = JSON.parse(mockWs.sentData[mockWs.sentData.length - 1]);
    expect(sentCtrl.type).toBe('CONTROL_CMD');
    expect(sentCtrl.payload.command).toBe('pause');

    client.disconnect();
  });
});
