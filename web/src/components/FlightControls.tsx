/**
 * Flight Controls Component.
 *
 * Provides:
 * - Operating mode switcher: AI (Deterministic / Stochastic) vs Manual (Human Pilot) vs Storm.
 * - Simulation flow commands: Pause, Resume, Reset, Simulation Speed.
 * - Robust keyboard input handler for Manual mode with focus-loss protection (blur/visibilitychange).
 * - Visual key indicator HUD for W (Main), A (Left RCS), D (Right RCS).
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import type { FlightMode, PolicyMode } from '../types/protocol';

interface FlightControlsProps {
  flightMode: FlightMode;
  policyMode: PolicyMode;
  isPaused: boolean;
  speedFactor: number;
  currentStep: number;
  onModeChange: (mode: FlightMode, policy?: PolicyMode) => void;
  onControlCmd: (command: 'pause' | 'resume' | 'reset' | 'set_speed', value?: number | null) => void;
  onSendAction: (step: number, action: 0 | 1 | 2 | 3) => void;
}

export const FlightControls: React.FC<FlightControlsProps> = ({
  flightMode,
  policyMode,
  isPaused,
  speedFactor,
  currentStep,
  onModeChange,
  onControlCmd,
  onSendAction,
}) => {
  // Pressed key tracking: Set of active keys ('KeyW', 'KeyA', 'KeyD', etc.)
  const [pressedKeys, setPressedKeys] = useState<{ [key: string]: boolean }>({});
  const [customSeed, setCustomSeed] = useState<string>('');

  const currentStepRef = useRef<number>(currentStep);
  currentStepRef.current = currentStep;

  // Resolve active action from pressed keys: 0=Coast, 1=Left RCS, 2=Main, 3=Right RCS
  const resolveAction = useCallback((keys: { [key: string]: boolean }): 0 | 1 | 2 | 3 => {
    const isMain = keys['KeyW'] || keys['ArrowUp'];
    const isLeft = keys['KeyA'] || keys['ArrowLeft'];
    const isRight = keys['KeyD'] || keys['ArrowRight'];

    if (isMain) return 2; // Main Engine takes precedence
    if (isLeft && !isRight) return 1; // Left RCS
    if (isRight && !isLeft) return 3; // Right RCS
    return 0; // Coast
  }, []);

  // Transmit action to backend when keys change in Manual mode
  const sendCurrentAction = useCallback(
    (keys: { [key: string]: boolean }) => {
      if (flightMode !== 'human') return; // Strict guard: never send actions in AI mode
      const act = resolveAction(keys);
      onSendAction(currentStepRef.current, act);
    },
    [flightMode, onSendAction, resolveAction]
  );

  // Keyboard Event Listeners with Focus-Loss Protection
  useEffect(() => {
    if (flightMode !== 'human') {
      setPressedKeys({});
      return;
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      // Prevent browser default scroll for simulation control keys
      if (['KeyW', 'KeyA', 'KeyD', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(e.code)) {
        e.preventDefault();
        setPressedKeys((prev) => {
          if (prev[e.code]) return prev; // Avoid repeated keydown events
          const next = { ...prev, [e.code]: true };
          sendCurrentAction(next);
          return next;
        });
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (['KeyW', 'KeyA', 'KeyD', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(e.code)) {
        e.preventDefault();
        setPressedKeys((prev) => {
          const next = { ...prev, [e.code]: false };
          sendCurrentAction(next);
          return next;
        });
      }
    };

    // Focus-loss protection: Clear all pressed keys on blur or tab switch to prevent stuck throttle
    const handleFocusLoss = () => {
      setPressedKeys({});
      sendCurrentAction({});
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleFocusLoss);
    document.addEventListener('visibilitychange', handleFocusLoss);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleFocusLoss);
      document.removeEventListener('visibilitychange', handleFocusLoss);
    };
  }, [flightMode, sendCurrentAction]);

  const activeAction = resolveAction(pressedKeys);

  return (
    <div className="bg-[#0F141C] border border-slate-800 rounded-lg p-3 font-mono text-xs flex flex-col gap-3 shadow-xl">
      {/* Flight Mode Selection */}
      <div>
        <div className="text-slate-400 text-[10px] font-semibold mb-2 flex items-center justify-between">
          <span>FLIGHT CONTROL REGIME</span>
          <span className="text-cyan-400 font-bold uppercase">{flightMode} MODE</span>
        </div>

        <div className="grid grid-cols-3 gap-1.5">
          <button
            type="button"
            onClick={() => onModeChange('ai', 'deterministic')}
            className={`py-2 px-1 text-center font-bold rounded border transition-all ${
              flightMode === 'ai' && policyMode === 'deterministic'
                ? 'bg-cyan-950/80 border-cyan-400 text-cyan-300 shadow-[0_0_10px_rgba(0,240,255,0.3)]'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            AI OPTIMAL
            <span className="block text-[8px] font-normal text-slate-500 mt-0.5">DETERMINISTIC</span>
          </button>

          <button
            type="button"
            onClick={() => onModeChange('ai', 'stochastic')}
            className={`py-2 px-1 text-center font-bold rounded border transition-all ${
              flightMode === 'ai' && policyMode === 'stochastic'
                ? 'bg-cyan-950/80 border-cyan-400 text-cyan-300 shadow-[0_0_10px_rgba(0,240,255,0.3)]'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            AI STOCHASTIC
            <span className="block text-[8px] font-normal text-slate-500 mt-0.5">EXPLORATORY</span>
          </button>

          <button
            type="button"
            onClick={() => onModeChange('human')}
            className={`py-2 px-1 text-center font-bold rounded border transition-all ${
              flightMode === 'human'
                ? 'bg-amber-950/80 border-amber-400 text-amber-300 shadow-[0_0_10px_rgba(255,179,0,0.3)]'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            MANUAL PILOT
            <span className="block text-[8px] font-normal text-slate-500 mt-0.5">HUMAN ARROWS</span>
          </button>
        </div>
      </div>

      {/* Manual Keyboard Controls HUD (Visible only when in Manual mode) */}
      {flightMode === 'human' ? (
        <div className="bg-[#141B26] p-2.5 rounded border border-amber-500/30 flex flex-col gap-2">
          <div className="flex justify-between items-center text-[10px]">
            <span className="text-amber-400 font-bold flex items-center gap-1.5">
              <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              KEYBOARD FLY-BY-WIRE ACTIVE
            </span>
            <span className="text-slate-400 text-[9px]">FOCUS WINDOW TO PILOT</span>
          </div>

          <div className="flex justify-center items-center gap-2 my-1">
            {/* Left RCS [A] */}
            <div
              className={`w-14 h-12 rounded flex flex-col items-center justify-center border font-bold transition-all ${
                pressedKeys['KeyA'] || pressedKeys['ArrowLeft']
                  ? 'bg-cyan-400 text-black border-cyan-300 shadow-[0_0_12px_rgba(0,240,255,0.6)] scale-95'
                  : 'bg-slate-900 border-slate-700 text-slate-300'
              }`}
            >
              <span className="text-sm">A / ←</span>
              <span className="text-[8px] opacity-75">LEFT RCS</span>
            </div>

            {/* Main Engine [W] */}
            <div
              className={`w-16 h-14 rounded flex flex-col items-center justify-center border font-bold transition-all ${
                pressedKeys['KeyW'] || pressedKeys['ArrowUp']
                  ? 'bg-amber-400 text-black border-amber-300 shadow-[0_0_14px_rgba(255,179,0,0.6)] scale-95'
                  : 'bg-slate-900 border-slate-700 text-slate-300'
              }`}
            >
              <span className="text-base font-extrabold">W / ↑</span>
              <span className="text-[8px] opacity-75">MAIN THRUST</span>
            </div>

            {/* Right RCS [D] */}
            <div
              className={`w-14 h-12 rounded flex flex-col items-center justify-center border font-bold transition-all ${
                pressedKeys['KeyD'] || pressedKeys['ArrowRight']
                  ? 'bg-cyan-400 text-black border-cyan-300 shadow-[0_0_12px_rgba(0,240,255,0.6)] scale-95'
                  : 'bg-slate-900 border-slate-700 text-slate-300'
              }`}
            >
              <span className="text-sm">D / →</span>
              <span className="text-[8px] opacity-75">RIGHT RCS</span>
            </div>
          </div>

          <div className="text-[9px] text-center text-slate-400">
            TRANSMITTED ACTION:{' '}
            <span className="text-cyan-300 font-bold">
              {activeAction === 0 && '0 (COAST)'}
              {activeAction === 1 && '1 (LEFT RCS)'}
              {activeAction === 2 && '2 (MAIN ENGINE)'}
              {activeAction === 3 && '3 (RIGHT RCS)'}
            </span>
          </div>
        </div>
      ) : (
        <div className="bg-[#141B26] p-2 rounded border border-slate-800 text-[10px] text-slate-400 flex items-center justify-between">
          <span>AI CONTROL:</span>
          <span className="text-emerald-400 font-semibold">
            PPO POLICY NETWORK AUTONOMOUS GUIDANCE
          </span>
        </div>
      )}

      {/* Simulation Lifecycle Commands: Pause, Resume, Reset */}
      <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800">
        <button
          type="button"
          onClick={() => onControlCmd(isPaused ? 'resume' : 'pause')}
          className={`py-2 px-3 rounded font-bold border transition-colors flex items-center justify-center gap-2 ${
            isPaused
              ? 'bg-emerald-950/80 border-emerald-400 text-emerald-300 hover:bg-emerald-900/80'
              : 'bg-amber-950/80 border-amber-500 text-amber-300 hover:bg-amber-900/80'
          }`}
        >
          {isPaused ? '▶ RESUME SIMULATION' : '⏸ PAUSE SIMULATION'}
        </button>

        <button
          type="button"
          onClick={() => {
            const seedNum = customSeed.trim() !== '' ? parseInt(customSeed, 10) : null;
            onControlCmd('reset', isNaN(seedNum as number) ? null : seedNum);
          }}
          className="py-2 px-3 rounded font-bold bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 transition-colors flex items-center justify-center gap-1.5"
        >
          🔄 RESET EPISODE
        </button>
      </div>

      {/* Speed Multiplier & Custom Seed */}
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        {/* Speed Controls */}
        <div className="flex items-center gap-1 bg-[#141B26] p-1.5 rounded border border-slate-800">
          <span className="text-slate-400 text-[9px] mr-1">SPEED:</span>
          {[0.5, 1.0, 1.5, 2.0].map((spd) => (
            <button
              key={spd}
              type="button"
              onClick={() => onControlCmd('set_speed', spd)}
              className={`flex-1 py-1 rounded font-bold ${
                speedFactor === spd
                  ? 'bg-cyan-500 text-black'
                  : 'bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              {spd}x
            </button>
          ))}
        </div>

        {/* Seed Input */}
        <div className="flex items-center gap-1 bg-[#141B26] p-1.5 rounded border border-slate-800">
          <span className="text-slate-400 text-[9px]">SEED:</span>
          <input
            type="number"
            placeholder="Auto"
            value={customSeed}
            onChange={(e) => setCustomSeed(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-200 text-[10px] focus:outline-none focus:border-cyan-400"
          />
        </div>
      </div>
    </div>
  );
};
