/**
 * High-Fidelity 2D Canvas Engineering Viewport.
 *
 * Renders authoritative Box2D simulation states in a dark, precision aerospace HUD.
 * Coordinates are rendered in Box2D simulation distance units.
 * Features:
 * - Dynamic camera framing: smoothly tracks the descending lander while keeping pad grounded,
 *   scaling up lander details (~2.5x larger near touchdown) with toggleable Overview mode.
 * - Precision rocket booster silhouette: aerospace alloy core, carbon interstage,
 *   titanium grid fins, gimbaled engine bell, and telescoping hydraulic landing legs.
 * - Accurate propulsion telemetry: plume length/intensity strictly scales with actuator throttle;
 *   absolute zero plumes on coast, cutoff, or terminal latch.
 * - Spaceport landing pad: concrete foundation, hazard striping, touchdown rings, and corner beacons.
 * - Projected touchdown point and ground shadow reticle.
 * - Calibrated altitude scale (strictly in simulation units 'u') and velocity vector (in 'u/s').
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { SessionReadyPayload, SimulationSnapshotPayload } from '../types/protocol';

interface SimulationCanvasProps {
  snapshot: SimulationSnapshotPayload | null;
  sessionReady: SessionReadyPayload | null;
  flightMode: 'ai' | 'human' | 'storm';
  onReopenDebrief?: () => void;
  hasDebrief?: boolean;
}

interface Point2D {
  x: number;
  y: number;
}

export const SimulationCanvas: React.FC<SimulationCanvasProps> = ({
  snapshot,
  sessionReady,
  flightMode,
  onReopenDebrief,
  hasDebrief = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const trajectoryRef = useRef<Point2D[]>([]);
  const lastStepRef = useRef<number>(-1);

  // Camera tracking mode: 'tracking' (dynamic zoom onto descending vehicle) vs 'overview' (full 20x15 field)
  const [cameraMode, setCameraMode] = useState<'tracking' | 'overview'>('tracking');
  const cameraModeRef = useRef<'tracking' | 'overview'>('tracking');
  cameraModeRef.current = cameraMode;

  // Smoothed camera bounding box
  const camBoundsRef = useRef({
    minX: -8.0,
    maxX: 8.0,
    minY: -0.8,
    maxY: 14.0,
  });

  // Maintain trajectory trail
  useEffect(() => {
    if (!snapshot) {
      trajectoryRef.current = [];
      lastStepRef.current = -1;
      return;
    }

    // Clear trajectory on episode reset
    if (snapshot.lifecycle.step < lastStepRef.current || snapshot.lifecycle.step === 0) {
      trajectoryRef.current = [];
    }
    lastStepRef.current = snapshot.lifecycle.step;

    // Append position
    trajectoryRef.current.push({
      x: snapshot.kinematics.pos_x,
      y: snapshot.kinematics.altitude,
    });

    if (trajectoryRef.current.length > 100) {
      trajectoryRef.current.shift();
    }
  }, [snapshot]);

  // Main Canvas render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;

      // 1. Clear background (Deep space / twilight horizon)
      renderSkyBackground(ctx, width, height);

      // 2. Camera framing calculations
      const cam = camBoundsRef.current;
      const isTracking = cameraModeRef.current === 'tracking';

      if (snapshot && isTracking) {
        const k = snapshot.kinematics;
        // Target bounds: frame pad center (0.0) and vehicle position with margin
        const targetHalfSpanX = Math.max(3.8, Math.abs(k.pos_x) + 2.5);
        const targetMinX = -targetHalfSpanX;
        const targetMaxX = targetHalfSpanX;
        const targetMinY = -0.8;
        // As altitude drops, max altitude smoothly lowers from ~14 down to 4.2 units
        const targetMaxY = Math.max(4.2, k.altitude + 2.2);

        // Smooth exponential lerp (0.07 per frame at 60fps)
        const lerpRate = 0.07;
        cam.minX += (targetMinX - cam.minX) * lerpRate;
        cam.maxX += (targetMaxX - cam.maxX) * lerpRate;
        cam.minY += (targetMinY - cam.minY) * lerpRate;
        cam.maxY += (targetMaxY - cam.maxY) * lerpRate;
      } else {
        // Full Overview Mode: Box2D world view
        const targetMinX = -10.0;
        const targetMaxX = 10.0;
        const targetMinY = -1.2;
        const targetMaxY = 14.5;
        const lerpRate = 0.08;
        cam.minX += (targetMinX - cam.minX) * lerpRate;
        cam.maxX += (targetMaxX - cam.maxX) * lerpRate;
        cam.minY += (targetMinY - cam.minY) * lerpRate;
        cam.maxY += (targetMaxY - cam.maxY) * lerpRate;
      }

      const worldSpanX = cam.maxX - cam.minX;
      const worldSpanY = cam.maxY - cam.minY;
      const padBottomMargin = 65; // px for ground and bottom telemetry

      const scale = Math.min(
        (width - 50) / worldSpanX,
        (height - padBottomMargin - 30) / worldSpanY
      );

      // Center X matches the camera center
      const camCenterX = (cam.minX + cam.maxX) * 0.5;
      const screenCenterX = width * 0.5 - camCenterX * scale;
      const groundY = height - padBottomMargin - (-cam.minY) * scale;

      // Coordinate transformation functions (Box2D sim units -> Screen px)
      const toScreenX = (bx: number) => screenCenterX + bx * scale;
      const toScreenY = (by: number) => groundY - by * scale;

      // 3. Render Technical Spaceport Grid
      renderGrid(ctx, width, height, screenCenterX, groundY, scale, cam.minX, cam.maxX, cam.maxY);

      // 4. Render Terrain Profile with Depth Shading
      if (sessionReady && sessionReady.terrain.length > 0) {
        renderTerrain(ctx, sessionReady.terrain, toScreenX, toScreenY, width, height);
      }

      // 5. Render Landing Pad (Helipad, hazard chevrons, beacons)
      renderLandingPad(ctx, sessionReady, toScreenX, toScreenY, groundY, scale);

      // 6. Render Descent Corridor Guides & Altitude Gates
      renderDescentCorridor(ctx, screenCenterX, groundY, scale, cam.maxY);

      // 7. Render Altitude Ladder on Margin (Honest units: 'u')
      renderAltitudeScale(ctx, width, groundY, toScreenY, cam.maxY);

      // 8. Render Trajectory Trail
      renderTrajectory(ctx, trajectoryRef.current, toScreenX, toScreenY);

      // 9. Render Projected Ground Footprint & Touchdown Predictor
      if (snapshot) {
        renderTouchdownPredictor(ctx, snapshot, toScreenX, groundY, scale);
      }

      // 10. Render Lander Booster Body & Actuator Plumes
      if (snapshot) {
        renderLander(ctx, snapshot, toScreenX, toScreenY, scale);
        renderVelocityVector(ctx, snapshot, toScreenX, toScreenY, scale);
        renderHudOverlay(
          ctx,
          snapshot,
          width,
          height,
          flightMode,
          cameraModeRef.current,
          hasDebrief
        );
      } else {
        renderWaitingOverlay(ctx, width, height);
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [snapshot, sessionReady, flightMode, hasDebrief]);

  // Handle window resizing
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Handle canvas clicks for interactive HUD controls (camera mode toggle & debrief reopen)
  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const clickX = (e.clientX - rect.left) * window.devicePixelRatio;
      const clickY = (e.clientY - rect.top) * window.devicePixelRatio;
      const width = canvas.width;

      // Check click on Camera Mode pill (Top right area: x in [width - 230, width - 20], y in [14, 48])
      if (clickX >= width - 230 && clickX <= width - 20 && clickY >= 14 && clickY <= 48) {
        setCameraMode((prev) => (prev === 'tracking' ? 'overview' : 'tracking'));
        return;
      }

      // Check click on Debrief pill if visible (Top right area below camera: y in [54, 86])
      if (hasDebrief && onReopenDebrief) {
        if (clickX >= width - 230 && clickX <= width - 20 && clickY >= 52 && clickY <= 86) {
          onReopenDebrief();
        }
      }
    },
    [hasDebrief, onReopenDebrief]
  );

  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden rounded-lg border border-slate-800 bg-[#080B10] shadow-2xl">
      <canvas
        ref={canvasRef}
        onClick={handleCanvasClick}
        className="w-full h-full block cursor-crosshair"
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

// =============================================================================
// Canvas Rendering Sub-routines
// =============================================================================

function renderSkyBackground(ctx: CanvasRenderingContext2D, w: number, h: number) {
  // Atmospheric twilight gradient
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0.0, '#05070B');
  grad.addColorStop(0.7, '#080D16');
  grad.addColorStop(1.0, '#0D1624');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  // Subtle starry sky background
  ctx.save();
  ctx.fillStyle = 'rgba(255, 255, 255, 0.25)';
  const starCount = 35;
  for (let i = 0; i < starCount; i++) {
    const sx = ((i * 137.5) % w);
    const sy = ((i * 93.7) % (h * 0.65));
    const r = (i % 3 === 0) ? 1.2 : 0.8;
    ctx.beginPath();
    ctx.arc(sx, sy, r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function renderGrid(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  centerX: number,
  groundY: number,
  scale: number,
  minX: number,
  maxX: number,
  maxY: number
) {
  ctx.save();
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
  ctx.lineWidth = 1;

  // Vertical lines every 2 Box2D simulation units
  const startX = Math.floor(minX / 2) * 2;
  const endX = Math.ceil(maxX / 2) * 2;
  for (let bx = startX; bx <= endX; bx += 2) {
    const x = centerX + bx * scale;
    if (x >= 0 && x <= w) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
  }

  // Horizontal lines every 2 Box2D simulation units above pad
  const endY = Math.ceil(maxY / 2) * 2;
  for (let by = 0; by <= endY; by += 2) {
    const y = groundY - by * scale;
    if (y >= 0 && y <= h) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
  }

  // Center vertical centerline (pad alignment axis)
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.18)';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(centerX, 0);
  ctx.lineTo(centerX, h);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.restore();
}

function renderTerrain(
  ctx: CanvasRenderingContext2D,
  terrain: [number, number][],
  toScreenX: (x: number) => number,
  toScreenY: (y: number) => number,
  w: number,
  h: number
) {
  if (terrain.length < 2) return;

  ctx.save();

  // Background Terrain Ridge (Parallax silhouette)
  ctx.beginPath();
  ctx.moveTo(toScreenX(terrain[0][0]), toScreenY(terrain[0][1] * 0.7 - 0.2));
  for (let i = 1; i < terrain.length; i++) {
    ctx.lineTo(toScreenX(terrain[i][0]), toScreenY(terrain[i][1] * 0.7 - 0.2));
  }
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fillStyle = '#0B1017';
  ctx.fill();

  // Foreground Primary Terrain
  ctx.beginPath();
  ctx.moveTo(toScreenX(terrain[0][0]), toScreenY(terrain[0][1]));
  for (let i = 1; i < terrain.length; i++) {
    ctx.lineTo(toScreenX(terrain[i][0]), toScreenY(terrain[i][1]));
  }
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fillStyle = '#101722';
  ctx.fill();

  // Terrain Crest Highlight Line
  ctx.strokeStyle = '#27384E';
  ctx.lineWidth = 1.8;
  ctx.stroke();

  ctx.restore();
}

function renderLandingPad(
  ctx: CanvasRenderingContext2D,
  ready: SessionReadyPayload | null,
  toScreenX: (x: number) => number,
  _toScreenY: (y: number) => number,
  groundY: number,
  scale: number
) {
  const padHalfWidth = ready ? Math.abs(ready.helipad_bounds[1] - ready.helipad_bounds[0]) * 0.5 : 2.0;
  const leftX = toScreenX(-padHalfWidth);
  const rightX = toScreenX(padHalfWidth);
  const centerX = toScreenX(0);
  const padY = groundY;
  const padWidth = rightX - leftX;
  const padThickness = Math.max(10, 0.45 * scale);

  ctx.save();

  // 1. Blast deflector apron beneath foundation
  ctx.fillStyle = '#111823';
  ctx.fillRect(leftX - 18, padY + 2, padWidth + 36, padThickness + 14);

  // 2. Concrete Foundation Block
  const padGrad = ctx.createLinearGradient(0, padY, 0, padY + padThickness);
  padGrad.addColorStop(0, '#1E293B');
  padGrad.addColorStop(1, '#0F172A');
  ctx.fillStyle = padGrad;
  ctx.fillRect(leftX, padY, padWidth, padThickness);

  ctx.strokeStyle = '#00F0FF';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(leftX, padY, padWidth, padThickness);

  // 3. High-Contrast Yellow/Black Hazard Striping on Pad Surface Edge
  ctx.save();
  ctx.beginPath();
  ctx.rect(leftX, padY, padWidth, 5);
  ctx.clip();
  ctx.fillStyle = '#FFB300';
  ctx.fillRect(leftX, padY, padWidth, 5);
  ctx.strokeStyle = '#000000';
  ctx.lineWidth = 4;
  for (let x = leftX - 10; x < rightX + 15; x += 14) {
    ctx.beginPath();
    ctx.moveTo(x, padY);
    ctx.lineTo(x + 10, padY + 5);
    ctx.stroke();
  }
  ctx.restore();

  // 4. Helipad Target Bullseye Rings
  const ringRadiusOuter = 2.0 * scale;
  const ringRadiusInner = 1.0 * scale;

  ctx.strokeStyle = 'rgba(0, 240, 255, 0.25)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(centerX, padY, ringRadiusOuter, ringRadiusOuter * 0.25, 0, 0, Math.PI * 2);
  ctx.stroke();

  ctx.strokeStyle = 'rgba(0, 240, 255, 0.45)';
  ctx.beginPath();
  ctx.ellipse(centerX, padY, ringRadiusInner, ringRadiusInner * 0.25, 0, 0, Math.PI * 2);
  ctx.stroke();

  // Center Touchdown Crosshair '+'
  ctx.strokeStyle = '#00F0FF';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(centerX - 8, padY);
  ctx.lineTo(centerX + 8, padY);
  ctx.moveTo(centerX, padY - 4);
  ctx.lineTo(centerX, padY + 4);
  ctx.stroke();

  // 5. Active Boundary Strobe Beacon Lights at Pad Corners
  const timeSec = Date.now() * 0.003;
  const beaconGlow = 0.6 + 0.4 * Math.sin(timeSec * 4);

  ctx.fillStyle = `rgba(0, 230, 118, ${beaconGlow})`;
  ctx.shadowColor = '#00E676';
  ctx.shadowBlur = 10;
  ctx.beginPath();
  ctx.arc(leftX, padY, 4, 0, Math.PI * 2);
  ctx.arc(rightX, padY, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;

  // 6. Pad Identification Label
  ctx.fillStyle = 'rgba(0, 240, 255, 0.7)';
  ctx.font = '10px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('TARGET PAD // [X=0.0u, Y=0.0u]', centerX, padY + padThickness + 14);

  ctx.restore();
}

function renderDescentCorridor(
  ctx: CanvasRenderingContext2D,
  centerX: number,
  groundY: number,
  scale: number,
  maxY: number
) {
  ctx.save();

  // Visual glideslope funnel (tapers from top down to pad boundary)
  const topY = groundY - maxY * scale;
  const leftTop = centerX - 4.5 * scale;
  const rightTop = centerX + 4.5 * scale;
  const leftPad = centerX - 1.8 * scale;
  const rightPad = centerX + 1.8 * scale;

  ctx.strokeStyle = 'rgba(0, 240, 255, 0.08)';
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 5]);

  ctx.beginPath();
  ctx.moveTo(leftTop, topY);
  ctx.lineTo(leftPad, groundY);
  ctx.moveTo(rightTop, topY);
  ctx.lineTo(rightPad, groundY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Altitude Gate Checkpoint lines (at 2u, 5u, 10u)
  [2, 5, 10].forEach((alt) => {
    if (alt <= maxY) {
      const gateY = groundY - alt * scale;
      const frac = 1.0 - alt / Math.max(14, maxY);
      const halfWidth = (1.8 + (4.5 - 1.8) * (1.0 - frac)) * scale;

      ctx.strokeStyle = 'rgba(0, 240, 255, 0.06)';
      ctx.beginPath();
      ctx.moveTo(centerX - halfWidth, gateY);
      ctx.lineTo(centerX + halfWidth, gateY);
      ctx.stroke();
    }
  });

  ctx.restore();
}

function renderAltitudeScale(
  ctx: CanvasRenderingContext2D,
  w: number,
  groundY: number,
  toScreenY: (y: number) => number,
  maxY: number
) {
  ctx.save();
  ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
  ctx.font = '10px monospace';
  ctx.textAlign = 'right';

  const marginX = w - 16;
  const step = maxY > 10 ? 2 : 1;

  for (let alt = step; alt <= Math.ceil(maxY); alt += step) {
    const y = toScreenY(alt);
    if (y >= 10 && y <= groundY - 10) {
      ctx.beginPath();
      ctx.moveTo(marginX - 6, y);
      ctx.lineTo(marginX, y);
      ctx.stroke();
      ctx.fillText(`${alt.toFixed(0)}u`, marginX - 10, y + 3);
    }
  }

  // Pad ground baseline reference
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.5)';
  ctx.fillStyle = '#00F0FF';
  ctx.beginPath();
  ctx.moveTo(marginX - 12, groundY);
  ctx.lineTo(marginX, groundY);
  ctx.stroke();
  ctx.fillText('0u (PAD)', marginX - 16, groundY + 3);

  ctx.restore();
}

function renderTrajectory(
  ctx: CanvasRenderingContext2D,
  points: Point2D[],
  toScreenX: (x: number) => number,
  toScreenY: (y: number) => number
) {
  if (points.length < 2) return;

  ctx.save();
  for (let i = 1; i < points.length; i++) {
    const alpha = (i / points.length) * 0.45;
    ctx.strokeStyle = `rgba(0, 240, 255, ${alpha})`;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(toScreenX(points[i - 1].x), toScreenY(points[i - 1].y));
    ctx.lineTo(toScreenX(points[i].x), toScreenY(points[i].y));
    ctx.stroke();
  }
  ctx.restore();
}

function renderTouchdownPredictor(
  ctx: CanvasRenderingContext2D,
  snap: SimulationSnapshotPayload,
  toScreenX: (x: number) => number,
  groundY: number,
  scale: number
) {
  const k = snap.kinematics;
  const projX = toScreenX(k.pos_x);

  ctx.save();

  // 1. Ground shadow / vertical projection reticle
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.25)';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 4]);
  ctx.beginPath();
  ctx.moveTo(projX, groundY);
  ctx.lineTo(projX, groundY - k.altitude * scale);
  ctx.stroke();
  ctx.setLineDash([]);

  // Ground shadow ellipse
  ctx.fillStyle = 'rgba(0, 240, 255, 0.15)';
  ctx.beginPath();
  ctx.ellipse(projX, groundY, 0.6 * scale, 3, 0, 0, Math.PI * 2);
  ctx.fill();

  // 2. Projected landing intercept point (if sinking at vy < -0.1)
  if (k.vel_y < -0.1 && k.altitude > 0.1) {
    const tGo = k.altitude / Math.abs(k.vel_y);
    const predX = k.pos_x + k.vel_x * tGo;
    const screenPredX = toScreenX(predX);

    const isSafeTarget = Math.abs(predX) <= 1.5;
    const predColor = isSafeTarget ? '#00E676' : '#FFB300';

    ctx.strokeStyle = predColor;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(screenPredX, groundY, 4, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = predColor;
    ctx.font = '8px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('EST TOUCHDOWN', screenPredX, groundY - 8);
  }

  ctx.restore();
}

function renderLander(
  ctx: CanvasRenderingContext2D,
  snap: SimulationSnapshotPayload,
  toScreenX: (x: number) => number,
  toScreenY: (y: number) => number,
  scale: number
) {
  const k = snap.kinematics;
  const p = snap.propulsion;
  const g = snap.landing_gear;

  // Lander center of mass in screen coordinates
  const px = toScreenX(k.pos_x);
  const py = toScreenY(k.altitude);

  // Proportional vehicle dimensions matching Box2D physical bounds (~0.93 wide, 1.4 tall)
  const bodyW = 0.88 * scale;
  const bodyH = 1.38 * scale;
  const halfW = bodyW * 0.5;
  const halfH = bodyH * 0.5;

  ctx.save();
  ctx.translate(px, py);
  // Box2D angle is counter-clockwise radians; Canvas rotation is clockwise: invert sign
  ctx.rotate(-k.angle);

  // STRICT ACTUATOR CHECK: Plumes must strictly cease upon cutoff or terminal state
  const isCutoff = snap.lifecycle.terminated || snap.lifecycle.truncated || p.throttle <= 0;

  // 1. Thruster Plumes (Rendered behind vehicle body)
  if (!isCutoff && (p.action === 2 || p.throttle > 0) && p.throttle > 0) {
    renderMainEnginePlume(ctx, bodyW, bodyH, p.throttle);
  }

  if (!snap.lifecycle.terminated && !snap.lifecycle.truncated) {
    if ((p.action === 1 || p.rcs_left > 0) && p.rcs_left > 0) {
      renderRcsPlume(ctx, -halfW, -halfH * 0.55, 'left', scale, p.rcs_left);
    }
    if ((p.action === 3 || p.rcs_right > 0) && p.rcs_right > 0) {
      renderRcsPlume(ctx, halfW, -halfH * 0.55, 'right', scale, p.rcs_right);
    }
  }

  // 2. Landing Gear Assemblies (Struts, shock cylinders, footpads)
  renderLandingLegs(ctx, halfW, halfH, scale, g.left_contact, g.right_contact);

  // 3. Rocket Fuselage (Aerospace booster silhouette)
  // Main Cylindrical Body
  const coreGrad = ctx.createLinearGradient(-halfW, 0, halfW, 0);
  coreGrad.addColorStop(0.0, '#E2E8F0');
  coreGrad.addColorStop(0.5, '#FFFFFF');
  coreGrad.addColorStop(1.0, '#CBD5E1');
  ctx.fillStyle = coreGrad;
  ctx.fillRect(-halfW, -halfH, bodyW, bodyH);

  // Longitudinal structural stringers
  ctx.strokeStyle = 'rgba(100, 116, 139, 0.3)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(-halfW * 0.35, -halfH);
  ctx.lineTo(-halfW * 0.35, halfH);
  ctx.moveTo(halfW * 0.35, -halfH);
  ctx.lineTo(halfW * 0.35, halfH);
  ctx.stroke();

  // Carbon-Composite Interstage Band
  ctx.fillStyle = '#0F172A';
  ctx.fillRect(-halfW, -halfH * 0.35, bodyW, bodyH * 0.18);
  ctx.fillStyle = '#334155';
  ctx.fillRect(-halfW, -halfH * 0.35, bodyW, 2);
  ctx.fillRect(-halfW, -halfH * 0.17, bodyW, 2);

  // Aerodynamic Ogive Nose Fairing
  ctx.fillStyle = '#1E293B';
  ctx.beginPath();
  ctx.moveTo(-halfW, -halfH);
  ctx.quadraticCurveTo(-halfW * 0.5, -halfH - bodyH * 0.45, 0, -halfH - bodyH * 0.45);
  ctx.quadraticCurveTo(halfW * 0.5, -halfH - bodyH * 0.45, halfW, -halfH);
  ctx.closePath();
  ctx.fill();

  // Dark Thermal Protection Nose Cap & Pitot Probe
  ctx.fillStyle = '#090D14';
  ctx.beginPath();
  ctx.arc(0, -halfH - bodyH * 0.42, 3, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = '#94A3B8';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(0, -halfH - bodyH * 0.45);
  ctx.lineTo(0, -halfH - bodyH * 0.55);
  ctx.stroke();

  // Titanium Grid Fins (Deflect subtly with angular velocity)
  const finTilt = Math.max(-0.35, Math.min(0.35, k.ang_vel * 0.2));
  renderGridFin(ctx, -halfW - 5, -halfH * 0.75, finTilt, 'left');
  renderGridFin(ctx, halfW + 1, -halfH * 0.75, finTilt, 'right');

  // External Avionics Raceway Conduits
  ctx.fillStyle = '#64748B';
  ctx.fillRect(-halfW - 1.5, -halfH * 0.8, 1.5, bodyH * 0.7);
  ctx.fillRect(halfW, -halfH * 0.8, 1.5, bodyH * 0.7);

  // Gimbaled Engine Nozzle Bell
  const gimbalAngle = Math.max(-0.25, Math.min(0.25, -k.vel_x * 0.1));
  ctx.save();
  ctx.translate(0, halfH);
  ctx.rotate(gimbalAngle);

  // Engine Bell Exterior
  ctx.fillStyle = '#334155';
  ctx.beginPath();
  ctx.moveTo(-halfW * 0.4, 0);
  ctx.lineTo(halfW * 0.4, 0);
  ctx.lineTo(halfW * 0.65, bodyH * 0.2);
  ctx.lineTo(-halfW * 0.65, bodyH * 0.2);
  ctx.closePath();
  ctx.fill();

  // Interior Throat Glow
  if (!isCutoff && p.throttle > 0) {
    ctx.fillStyle = '#FF9100';
    ctx.beginPath();
    ctx.ellipse(0, bodyH * 0.18, halfW * 0.5, 3, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  // Booster Body Outer Stroke
  ctx.strokeStyle = '#00F0FF';
  ctx.lineWidth = 1.2;
  ctx.strokeRect(-halfW, -halfH, bodyW, bodyH);

  // Center of Mass Reticle
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.45)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(0, 0, 3.5, 0, Math.PI * 2);
  ctx.moveTo(-6, 0);
  ctx.lineTo(6, 0);
  ctx.moveTo(0, -6);
  ctx.lineTo(0, 6);
  ctx.stroke();

  ctx.restore();
}

function renderGridFin(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  tilt: number,
  _side: 'left' | 'right'
) {
  ctx.save();
  ctx.translate(x + 2, y + 4);
  ctx.rotate(tilt);

  ctx.fillStyle = '#475569';
  ctx.fillRect(-2, -4, 5, 8);
  ctx.strokeStyle = '#00F0FF';
  ctx.lineWidth = 0.8;
  ctx.strokeRect(-2, -4, 5, 8);

  // Titanium cross-hatching
  ctx.beginPath();
  ctx.moveTo(-2, -1);
  ctx.lineTo(3, -1);
  ctx.moveTo(-2, 2);
  ctx.lineTo(3, 2);
  ctx.stroke();

  ctx.restore();
}

function renderLandingLegs(
  ctx: CanvasRenderingContext2D,
  halfW: number,
  halfH: number,
  scale: number,
  leftContact: boolean,
  rightContact: boolean
) {
  const legSpanX = 0.58 * scale;
  const legDropY = 0.592 * scale; // Exact Box2D leg offset calibration

  ctx.save();
  ctx.lineWidth = 2.2;

  // Left Leg Main Strut
  ctx.strokeStyle = leftContact ? '#00E676' : '#94A3B8';
  ctx.beginPath();
  ctx.moveTo(-halfW * 0.75, halfH * 0.65);
  ctx.lineTo(-halfW - legSpanX, halfH + legDropY);
  ctx.stroke();

  // Left Telescoping Hydraulic Piston
  ctx.strokeStyle = leftContact ? '#00E676' : '#64748B';
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(-halfW * 0.35, halfH * 0.85);
  ctx.lineTo(-halfW - legSpanX * 0.5, halfH + legDropY * 0.55);
  ctx.stroke();

  // Left Articulated Footpad
  ctx.fillStyle = leftContact ? '#00E676' : '#64748B';
  ctx.shadowColor = leftContact ? '#00E676' : 'transparent';
  ctx.shadowBlur = leftContact ? 10 : 0;
  ctx.fillRect(-halfW - legSpanX - 5, halfH + legDropY - 2, 10, 3.5);

  // Right Leg Main Strut
  ctx.lineWidth = 2.2;
  ctx.strokeStyle = rightContact ? '#00E676' : '#94A3B8';
  ctx.beginPath();
  ctx.moveTo(halfW * 0.75, halfH * 0.65);
  ctx.lineTo(halfW + legSpanX, halfH + legDropY);
  ctx.stroke();

  // Right Telescoping Hydraulic Piston
  ctx.strokeStyle = rightContact ? '#00E676' : '#64748B';
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(halfW * 0.35, halfH * 0.85);
  ctx.lineTo(halfW + legSpanX * 0.5, halfH + legDropY * 0.55);
  ctx.stroke();

  // Right Articulated Footpad
  ctx.fillStyle = rightContact ? '#00E676' : '#64748B';
  ctx.shadowColor = rightContact ? '#00E676' : 'transparent';
  ctx.shadowBlur = rightContact ? 10 : 0;
  ctx.fillRect(halfW + legSpanX - 5, halfH + legDropY - 2, 10, 3.5);

  ctx.restore();
}

function renderMainEnginePlume(
  ctx: CanvasRenderingContext2D,
  bodyW: number,
  bodyH: number,
  throttle: number
) {
  // Proportional sizing directly based on actuator throttle
  const plumeLength = (bodyH * 0.85 + Math.random() * bodyH * 0.25) * throttle;
  const plumeW = bodyW * 0.55 * Math.max(0.6, throttle);
  const startY = bodyH * 0.5 + bodyH * 0.2;

  ctx.save();

  // Outer Radiant Exhaust Glow
  const grad = ctx.createLinearGradient(0, startY, 0, startY + plumeLength);
  grad.addColorStop(0.0, '#FFFFFF');
  grad.addColorStop(0.15, '#00F0FF');
  grad.addColorStop(0.45, '#FF9100');
  grad.addColorStop(0.8, '#FF3D00');
  grad.addColorStop(1.0, 'rgba(255, 61, 0, 0)');

  ctx.fillStyle = grad;
  ctx.shadowColor = '#FF9100';
  ctx.shadowBlur = 14;

  ctx.beginPath();
  ctx.moveTo(-plumeW * 0.5, startY);
  ctx.quadraticCurveTo(-plumeW * 0.8, startY + plumeLength * 0.55, 0, startY + plumeLength);
  ctx.quadraticCurveTo(plumeW * 0.8, startY + plumeLength * 0.55, plumeW * 0.5, startY);
  ctx.closePath();
  ctx.fill();

  // Inner Supersonic Shock Core
  ctx.fillStyle = '#FFFFFF';
  ctx.shadowColor = '#00F0FF';
  ctx.shadowBlur = 8;
  ctx.beginPath();
  ctx.moveTo(-plumeW * 0.25, startY);
  ctx.lineTo(0, startY + plumeLength * 0.45);
  ctx.lineTo(plumeW * 0.25, startY);
  ctx.closePath();
  ctx.fill();

  // Diamond Shock Disc
  if (throttle > 0.5) {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.ellipse(0, startY + plumeLength * 0.28, plumeW * 0.2, 2.5, 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.restore();
}

function renderRcsPlume(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  direction: 'left' | 'right',
  scale: number,
  intensity: number
) {
  const plumeLen = (0.45 + Math.random() * 0.25) * scale * intensity;
  const plumeSpread = 0.18 * scale * intensity;
  const sign = direction === 'left' ? -1 : 1;

  ctx.save();
  ctx.fillStyle = 'rgba(0, 240, 255, 0.75)';
  ctx.shadowColor = '#00F0FF';
  ctx.shadowBlur = 8;

  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + sign * plumeLen, y - plumeSpread);
  ctx.lineTo(x + sign * plumeLen, y + plumeSpread);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function renderVelocityVector(
  ctx: CanvasRenderingContext2D,
  snap: SimulationSnapshotPayload,
  toScreenX: (x: number) => number,
  toScreenY: (y: number) => number,
  scale: number
) {
  const k = snap.kinematics;
  const px = toScreenX(k.pos_x);
  const py = toScreenY(k.altitude);

  // Calibrated velocity vector scaling: 1 u/s = 0.4 scale px
  const vx = k.vel_x * scale * 0.4;
  const vy = -k.vel_y * scale * 0.4; // Canvas Y inverted
  const speed = Math.sqrt(k.vel_x * k.vel_x + k.vel_y * k.vel_y);

  if (speed < 0.05) return;

  // Color code based on descent velocity threshold
  let color = '#00E676'; // Safe sink rate
  if (Math.abs(k.vel_y) > 2.0) {
    color = '#FF1744'; // Danger
  } else if (Math.abs(k.vel_y) > 1.0) {
    color = '#FFB300'; // Caution
  }

  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 1.8;

  ctx.beginPath();
  ctx.moveTo(px, py);
  ctx.lineTo(px + vx, py + vy);
  ctx.stroke();

  // Vector Arrowhead
  const angle = Math.atan2(vy, vx);
  ctx.beginPath();
  ctx.moveTo(px + vx, py + vy);
  ctx.lineTo(
    px + vx - 7 * Math.cos(angle - Math.PI / 6),
    py + vy - 7 * Math.sin(angle - Math.PI / 6)
  );
  ctx.lineTo(
    px + vx - 7 * Math.cos(angle + Math.PI / 6),
    py + vy - 7 * Math.sin(angle + Math.PI / 6)
  );
  ctx.closePath();
  ctx.fill();

  // Speed Readout Tag next to arrow
  ctx.font = '9px monospace';
  ctx.textAlign = 'left';
  ctx.fillText(`${speed.toFixed(2)} u/s`, px + vx + 5, py + vy + 3);

  ctx.restore();
}

function renderHudOverlay(
  ctx: CanvasRenderingContext2D,
  snap: SimulationSnapshotPayload,
  w: number,
  _h: number,
  flightMode: string,
  cameraMode: string,
  hasDebrief: boolean
) {
  const k = snap.kinematics;
  const l = snap.lifecycle;

  ctx.save();
  ctx.font = '11px monospace';

  // 1. Top-Left HUD Card: Flight Regime & Lifecycle Phase
  ctx.fillStyle = 'rgba(11, 14, 20, 0.85)';
  ctx.fillRect(14, 14, 230, 68);
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.35)';
  ctx.lineWidth = 1;
  ctx.strokeRect(14, 14, 230, 68);

  ctx.fillStyle = '#00F0FF';
  ctx.textAlign = 'left';
  ctx.fillText(`MODE: ${flightMode.toUpperCase()} // STEP ${l.step}/1000`, 24, 32);

  ctx.fillStyle = '#E2E8F0';
  ctx.fillText(`DURATION: ${l.sim_time.toFixed(2)}s (${(l.sim_time * 50).toFixed(0)} ticks)`, 24, 48);

  // Status Badge
  const statusColor = l.terminated || l.truncated
    ? l.outcome?.includes('SUCCESS')
      ? '#00E676'
      : '#FF1744'
    : '#00E676';
  ctx.fillStyle = statusColor;
  ctx.fillText(`STATUS  : ${l.touchdown_phase}`, 24, 64);

  // 2. Top-Right Area: Camera Mode Pill & Glideslope Alignment
  ctx.textAlign = 'right';
  const camPillW = 210;
  const pillX = w - camPillW - 14;

  ctx.fillStyle = 'rgba(11, 14, 20, 0.85)';
  ctx.fillRect(pillX, 14, camPillW, 34);
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.35)';
  ctx.lineWidth = 1;
  ctx.strokeRect(pillX, 14, camPillW, 34);

  ctx.fillStyle = '#94A3B8';
  ctx.fillText('CAMERA:', pillX + 60, 34);
  ctx.fillStyle = cameraMode === 'tracking' ? '#00F0FF' : '#FFB300';
  ctx.fillText(
    cameraMode === 'tracking' ? 'TRACKING [AUTO]' : 'OVERVIEW [WIDE]',
    pillX + camPillW - 10,
    34
  );

  // 3. Glideslope Alignment Indicator below camera pill
  const isAligned = Math.abs(k.pos_x) <= 1.0 && Math.abs(k.angle * 57.3) <= 10.0;
  ctx.fillStyle = 'rgba(11, 14, 20, 0.85)';
  ctx.fillRect(pillX, 52, camPillW, 26);
  ctx.strokeStyle = isAligned ? 'rgba(0, 230, 118, 0.3)' : 'rgba(255, 179, 0, 0.3)';
  ctx.strokeRect(pillX, 52, camPillW, 26);

  ctx.fillStyle = isAligned ? '#00E676' : '#FFB300';
  ctx.fillText(
    isAligned ? 'GLIDESLOPE: ALIGNED' : `CORRECTION: ΔX ${k.pos_x >= 0 ? '+' : ''}${k.pos_x.toFixed(2)}u`,
    pillX + camPillW - 10,
    69
  );

  // 4. Reopen Debrief Pill (if debrief dismissed and available)
  if (hasDebrief) {
    ctx.fillStyle = 'rgba(0, 240, 255, 0.15)';
    ctx.fillRect(pillX, 82, camPillW, 24);
    ctx.strokeStyle = '#00F0FF';
    ctx.strokeRect(pillX, 82, camPillW, 24);
    ctx.fillStyle = '#00F0FF';
    ctx.fillText('📋 VIEW DEBRIEF MODAL', pillX + camPillW - 10, 98);
  }

  ctx.restore();
}

function renderWaitingOverlay(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.save();
  ctx.fillStyle = 'rgba(0, 240, 255, 0.8)';
  ctx.font = '13px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('STANDBY // CONNECTING TO HEADLESS SIMULATION ENGINE...', w * 0.5, h * 0.5);
  ctx.restore();
}
