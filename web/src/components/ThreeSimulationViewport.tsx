/**
 * Three.js 3D Simulation Viewport Component.
 *
 * Renders the authoritative Box2D simulation in high-fidelity 3D WebGL:
 * - Procedural orbital booster with gimbaled engine, grid fins, and articulated landing legs.
 * - Complete 3D spaceport with launch towers, fuel tanks, hazard markings, and beacons.
 * - Real-time synchronized animation consuming identical WebSocket snapshots.
 * - Follow-camera (dynamic tracking) and Overview-camera modes with interactive mouse orbit.
 * - Graphics quality presets (High vs Low-Power) and WebGL capability check with graceful fallback.
 * - Built-in FPS performance measurement.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import type { SessionReadyPayload, SimulationSnapshotPayload } from '../types/protocol';
import { createBoosterModel, updateBoosterModel } from '../three/boosterModel';
import { createSpaceportScene, updateSpaceportScene } from '../three/spaceportScene';
import { computeCameraTargets } from '../three/coordinateMapping';

interface ThreeSimulationViewportProps {
  snapshot: SimulationSnapshotPayload | null;
  sessionReady: SessionReadyPayload | null;
  flightMode: 'ai' | 'human' | 'storm';
  onReopenDebrief?: () => void;
  hasDebrief?: boolean;
  onFallbackTo2D?: () => void;
}

/**
 * Recursively disposes geometries, materials, and all texture properties
 * in a Three.js hierarchy (Meshes, Lines, Points, Lights) to guarantee
 * zero GPU memory leaks on unmount or quality preset switching.
 */
function disposeHierarchy(obj: THREE.Object3D): void {
  obj.traverse((child) => {
    const item = child as any;
    if (item.geometry && typeof item.geometry.dispose === 'function') {
      item.geometry.dispose();
    }
    if (item.material) {
      const mats = Array.isArray(item.material) ? item.material : [item.material];
      mats.forEach((mat: any) => {
        // Dispose all attached texture properties on the material (e.g. map, envMap, bumpMap)
        for (const key of Object.keys(mat)) {
          const prop = mat[key];
          if (
            prop &&
            typeof prop === 'object' &&
            prop.isTexture &&
            typeof prop.dispose === 'function'
          ) {
            prop.dispose();
          }
        }
        if (typeof mat.dispose === 'function') {
          mat.dispose();
        }
      });
    }
  });
}

export const ThreeSimulationViewport: React.FC<ThreeSimulationViewportProps> = ({
  snapshot,
  sessionReady,
  flightMode,
  onReopenDebrief,
  hasDebrief = false,
  onFallbackTo2D,
}) => {
  const mountRef = useRef<HTMLDivElement | null>(null);

  // Viewport Settings State
  const [cameraMode, setCameraMode] = useState<'follow' | 'overview'>('follow');
  const [graphicsQuality, setGraphicsQuality] = useState<'high' | 'low'>('high');
  const [measuredFps, setMeasuredFps] = useState<number>(60);
  const [webGlSupported, setWebGlSupported] = useState<boolean>(true);

  // Ref mirrors for render loop access
  const cameraModeRef = useRef<'follow' | 'overview'>(cameraMode);
  cameraModeRef.current = cameraMode;

  const qualityRef = useRef<'high' | 'low'>(graphicsQuality);
  qualityRef.current = graphicsQuality;

  const snapshotRef = useRef<SimulationSnapshotPayload | null>(snapshot);
  snapshotRef.current = snapshot;

  // Interactive Orbit / Pan State
  const mouseStateRef = useRef({
    isDragging: false,
    prevX: 0,
    prevY: 0,
    orbitTheta: 0.0, // Horizontal rotation offset (radians)
    orbitPhi: 0.0,   // Vertical elevation offset (radians)
    zoomDist: 0.0,   // Manual zoom offset
  });

  // Verify WebGL availability on mount
  useEffect(() => {
    try {
      const testCanvas = document.createElement('canvas');
      const gl = testCanvas.getContext('webgl') || testCanvas.getContext('experimental-webgl');
      if (!gl) {
        setWebGlSupported(false);
      }
    } catch {
      setWebGlSupported(false);
    }
  }, []);

  // Main Three.js Lifecycle
  useEffect(() => {
    if (!webGlSupported) return;
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;

    // 1. Three.js Renderer Setup
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: qualityRef.current === 'high',
        powerPreference: 'high-performance',
        alpha: false,
      });
    } catch {
      setWebGlSupported(false);
      return;
    }

    const dpr = qualityRef.current === 'high' ? Math.min(window.devicePixelRatio, 1.5) : 1.0;
    renderer.setPixelRatio(dpr);
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = qualityRef.current === 'high';
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const canvas = renderer.domElement;
    container.appendChild(canvas);

    // 2. Camera Setup
    const camera = new THREE.PerspectiveCamera(48, width / height, 0.5, 120);
    camera.position.set(0, 10, 20);

    // 3. Create Scene & Environment
    const spaceport = createSpaceportScene(sessionReady, qualityRef.current);
    const booster = createBoosterModel(qualityRef.current);
    spaceport.scene.add(booster.root);

    // Smoothed Camera Coordinates
    const smoothedCamPos = new THREE.Vector3(0, 10, 20);
    const smoothedCamTarget = new THREE.Vector3(0, 3, 0);

    // FPS Measurement tracking
    let frameCount = 0;
    let lastFpsTime = performance.now();
    let animId: number;

    // Context loss & recovery handlers
    const handleContextLost = (e: Event) => {
      e.preventDefault();
      cancelAnimationFrame(animId);
      setWebGlSupported(false);
    };

    const handleContextRestored = () => {
      console.warn('[WebGL] WebGL context restored by browser.');
      setWebGlSupported(true);
    };

    canvas.addEventListener('webglcontextlost', handleContextLost, false);
    canvas.addEventListener('webglcontextrestored', handleContextRestored, false);

    // Expose renderer stats for automated performance testing
    if (typeof window !== 'undefined') {
      (window as any).__THREE_PERF__ = {
        getStats: () => ({
          fps: measuredFps,
          calls: renderer.info.render.calls,
          triangles: renderer.info.render.triangles,
          geometries: renderer.info.memory.geometries,
          textures: renderer.info.memory.textures,
        }),
      };
    }

    // 4. Animation / Render Loop
    const renderLoop = () => {
      animId = requestAnimationFrame(renderLoop);

      // Measure FPS
      frameCount++;
      const now = performance.now();
      if (now - lastFpsTime >= 1000) {
        setMeasuredFps(Math.round((frameCount * 1000) / (now - lastFpsTime)));
        frameCount = 0;
        lastFpsTime = now;
      }

      const snap = snapshotRef.current;
      const k = snap ? snap.kinematics : null;

      // Update booster model actuators and contacts
      updateBoosterModel(booster, snap, qualityRef.current);

      // Update spaceport dynamic markers, beacons, and velocity vector
      updateSpaceportScene(spaceport, snap);

      // Camera Position Calculations
      const posX = k ? k.pos_x : 0.0;
      const altitude = k ? k.altitude : 6.0;
      const targets = computeCameraTargets(cameraModeRef.current, posX, altitude);

      const ms = mouseStateRef.current;
      // Base camera eye position with manual orbit offsets
      const desiredEye = new THREE.Vector3(
        targets.eye.x + Math.sin(ms.orbitTheta) * (targets.eye.z + ms.zoomDist),
        targets.eye.y + ms.orbitPhi,
        Math.cos(ms.orbitTheta) * (targets.eye.z + ms.zoomDist)
      );

      const desiredTarget = new THREE.Vector3(targets.target.x, targets.target.y, targets.target.z);

      // Smooth camera interpolation (lerp factor 0.08)
      smoothedCamPos.lerp(desiredEye, 0.08);
      smoothedCamTarget.lerp(desiredTarget, 0.08);

      camera.position.copy(smoothedCamPos);
      camera.lookAt(smoothedCamTarget);

      // Render Scene
      renderer.render(spaceport.scene, camera);
    };

    animId = requestAnimationFrame(renderLoop);

    // 5. Handle Resize
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    // 6. Cleanup on Unmount
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      canvas.removeEventListener('webglcontextlost', handleContextLost);
      canvas.removeEventListener('webglcontextrestored', handleContextRestored);

      if (typeof window !== 'undefined') {
        delete (window as any).__THREE_PERF__;
      }

      // Deep dispose scene objects
      disposeHierarchy(spaceport.scene);

      // Dispose Renderer and canvas
      if (canvas && container.contains(canvas)) {
        container.removeChild(canvas);
      }
      renderer.dispose();
    };
  }, [sessionReady, webGlSupported, graphicsQuality]);

  // Interactive Orbit Handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    mouseStateRef.current.isDragging = true;
    mouseStateRef.current.prevX = e.clientX;
    mouseStateRef.current.prevY = e.clientY;
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!mouseStateRef.current.isDragging) return;
    const dx = e.clientX - mouseStateRef.current.prevX;
    const dy = e.clientY - mouseStateRef.current.prevY;
    mouseStateRef.current.prevX = e.clientX;
    mouseStateRef.current.prevY = e.clientY;

    // Apply orbit delta
    mouseStateRef.current.orbitTheta -= dx * 0.008;
    mouseStateRef.current.orbitPhi = Math.max(
      -4.0,
      Math.min(8.0, mouseStateRef.current.orbitPhi + dy * 0.02)
    );
  }, []);

  const handleMouseUp = useCallback(() => {
    mouseStateRef.current.isDragging = false;
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    mouseStateRef.current.zoomDist = Math.max(
      -6.0,
      Math.min(18.0, mouseStateRef.current.zoomDist + e.deltaY * 0.01)
    );
  }, []);

  const handleResetCamera = useCallback(() => {
    mouseStateRef.current.orbitTheta = 0.0;
    mouseStateRef.current.orbitPhi = 0.0;
    mouseStateRef.current.zoomDist = 0.0;
  }, []);

  // WebGL Unsupported Fallback State
  if (!webGlSupported) {
    return (
      <div className="relative w-full h-full flex flex-col items-center justify-center p-6 bg-[#080B10] border border-amber-500/40 rounded-lg font-mono text-center">
        <div className="text-3xl mb-2">⚠️</div>
        <div className="text-amber-400 font-bold text-sm">WEBGL HARDWARE ACCELERATION UNAVAILABLE</div>
        <div className="text-slate-400 text-xs mt-2 max-w-md">
          Your browser or graphics environment does not support WebGL 3D rendering. Falling back to the
          authoritative 2D Canvas engineering interface.
        </div>
        {onFallbackTo2D && (
          <button
            type="button"
            onClick={onFallbackTo2D}
            className="mt-4 px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs rounded transition-colors shadow-lg"
          >
            SWITCH TO 2D ENGINEERING VIEW
          </button>
        )}
      </div>
    );
  }

  const l = snapshot?.lifecycle;

  return (
    <div
      className="relative w-full h-full overflow-hidden rounded-lg border border-slate-800 bg-[#06090F] shadow-2xl select-none"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
    >
      {/* 3D WebGL Canvas Container */}
      <div ref={mountRef} className="w-full h-full block cursor-grab active:cursor-grabbing" />

      {/* Top-Left Status HUD */}
      <div className="absolute top-3 left-3 bg-[#0B0E14]/85 border border-cyan-500/30 p-2.5 rounded font-mono text-xs flex flex-col gap-1 pointer-events-none shadow-xl">
        <div className="text-cyan-400 font-bold flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span>3D CINEMATIC VIEW // {flightMode.toUpperCase()}</span>
        </div>
        <div className="text-slate-300 text-[10px]">
          STEP: <span className="text-slate-100 font-bold">{l ? l.step : 0}</span>/1000 &nbsp;•&nbsp;
          DURATION: <span className="text-slate-100 font-bold">{l ? l.sim_time.toFixed(2) : '0.00'}s</span>
        </div>
        <div className="text-[10px] flex items-center gap-2 mt-0.5">
          <span
            className={`font-bold ${
              l?.terminated || l?.truncated
                ? l?.outcome?.includes('SUCCESS')
                  ? 'text-emerald-400'
                  : 'text-rose-400'
                : 'text-emerald-400'
            }`}
          >
            STATUS: {l ? l.touchdown_phase : 'STANDBY'}
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">
            FPS: <span className={measuredFps >= 50 ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>{measuredFps}</span>
          </span>
        </div>
      </div>

      {/* Top-Right Interactive Camera & Quality Controls */}
      <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5 font-mono text-xs">
        {/* Camera Mode Toggle & Quality Controls */}
        <div className="flex items-center gap-1.5 bg-[#0B0E14]/90 border border-slate-800 p-1 rounded shadow-xl">
          <button
            type="button"
            onClick={() => setCameraMode((prev) => (prev === 'follow' ? 'overview' : 'follow'))}
            className={`px-2 py-1 rounded text-[10px] font-bold border transition-colors ${
              cameraMode === 'follow'
                ? 'bg-cyan-950/80 border-cyan-400 text-cyan-300 shadow-[0_0_8px_rgba(0,240,255,0.4)]'
                : 'bg-slate-900 border-slate-700 text-slate-300 hover:text-white'
            }`}
          >
            {cameraMode === 'follow' ? 'CAM: FOLLOW' : 'CAM: OVERVIEW'}
          </button>

          <button
            type="button"
            onClick={() => setGraphicsQuality((prev) => (prev === 'high' ? 'low' : 'high'))}
            className={`px-2 py-1 rounded text-[10px] font-bold border transition-colors ${
              graphicsQuality === 'high'
                ? 'bg-emerald-950/80 border-emerald-400 text-emerald-300'
                : 'bg-amber-950/80 border-amber-400 text-amber-300'
            }`}
            title="Toggle between High Quality (Shadows, FX) and Low-Power (Fast rendering)"
          >
            {graphicsQuality === 'high' ? 'QUALITY: HIGH' : 'LOW-POWER'}
          </button>

          <button
            type="button"
            onClick={handleResetCamera}
            className="px-1.5 py-1 rounded text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
            title="Reset orbit camera perspective"
          >
            RESET
          </button>
        </div>

        {/* Re-open Debrief Pill (if available) */}
        {hasDebrief && onReopenDebrief && (
          <button
            type="button"
            onClick={onReopenDebrief}
            className="bg-[#0B0E14]/90 hover:bg-cyan-950 border border-cyan-400/80 px-2.5 py-1 rounded text-[10px] font-bold text-cyan-300 shadow-xl transition-colors"
          >
            📋 VIEW DEBRIEF MODAL
          </button>
        )}
      </div>

      {/* Bottom Hint Indicator */}
      <div className="absolute bottom-2 left-3 text-[9px] font-mono text-slate-500 pointer-events-none">
        DRAG TO ORBIT VIEW • SCROLL TO ZOOM • 3D PRESENTATION LAYER (AUTHORITATIVE BOX2D PHYSICS)
      </div>
    </div>
  );
};
