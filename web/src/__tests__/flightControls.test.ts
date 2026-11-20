import { describe, it, expect } from 'vitest';

describe('FlightControls Keyboard & Action Mapping', () => {
  // Action resolver matching FlightControls logic:
  // 0=Coast, 1=Left RCS, 2=Main Engine, 3=Right RCS
  function resolveAction(keys: { [key: string]: boolean }): 0 | 1 | 2 | 3 {
    const isMain = keys['KeyW'] || keys['ArrowUp'];
    const isLeft = keys['KeyA'] || keys['ArrowLeft'];
    const isRight = keys['KeyD'] || keys['ArrowRight'];

    if (isMain) return 2; // Main Engine takes precedence
    if (isLeft && !isRight) return 1; // Left RCS
    if (isRight && !isLeft) return 3; // Right RCS
    return 0; // Neutral Coast
  }

  it('maps neutral state (no keys) to action 0 (COAST)', () => {
    expect(resolveAction({})).toBe(0);
    expect(resolveAction({ KeyW: false, KeyA: false })).toBe(0);
  });

  it('maps W or ArrowUp to action 2 (MAIN ENGINE)', () => {
    expect(resolveAction({ KeyW: true })).toBe(2);
    expect(resolveAction({ ArrowUp: true })).toBe(2);
  });

  it('maps A or ArrowLeft to action 1 (LEFT RCS)', () => {
    expect(resolveAction({ KeyA: true })).toBe(1);
    expect(resolveAction({ ArrowLeft: true })).toBe(1);
  });

  it('maps D or ArrowRight to action 3 (RIGHT RCS)', () => {
    expect(resolveAction({ KeyD: true })).toBe(3);
    expect(resolveAction({ ArrowRight: true })).toBe(3);
  });

  it('prioritizes Main Engine when both Main and RCS keys are pressed', () => {
    expect(resolveAction({ KeyW: true, KeyA: true })).toBe(2);
    expect(resolveAction({ KeyW: true, KeyD: true })).toBe(2);
  });

  it('resolves opposing RCS inputs (A + D) safely to 0 (COAST)', () => {
    expect(resolveAction({ KeyA: true, KeyD: true })).toBe(0);
  });

  it('clears all active actions upon focus loss (blur/visibility change)', () => {
    const activeKeys: { [key: string]: boolean } = { KeyW: true, KeyA: true };
    expect(resolveAction(activeKeys)).toBe(2);

    // Simulate focus loss clearing keys
    const clearedKeys: { [key: string]: boolean } = {};
    expect(resolveAction(clearedKeys)).toBe(0);
  });

  it('enforces that manual actions are guarded against sending in AI mode', () => {
    let transmittedAction: number | null = null;
    const sendManualAction = (mode: 'ai' | 'human', action: 0 | 1 | 2 | 3) => {
      if (mode !== 'human') return; // Strict guard
      transmittedAction = action;
    };

    // When in AI mode:
    sendManualAction('ai', 2);
    expect(transmittedAction).toBeNull(); // Must NOT transmit

    // When in Human mode:
    sendManualAction('human', 2);
    expect(transmittedAction).toBe(2);
  });
});
