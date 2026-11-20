/**
 * Procedural 3D Reusable Orbital Booster Model.
 *
 * Implements a high-detail aerospace rocket booster using pure Three.js procedural geometry:
 * - Core cylindrical booster fuselage with aerospace alloy finish and longitudinal raceways.
 * - Carbon-composite interstage band.
 * - Aerodynamic ogive nose cone with thermal protection cap, RCS pods, and pitot boom.
 * - 4 Foldable titanium lattice grid fins with dynamic deflection reacting to angular velocity.
 * - Gimbaled rocket engine nozzle bell with high-temperature throat core.
 * - Supersonic diamond-shock main engine plume scaling strictly with actuator throttle.
 * - Directional cold-gas RCS puffs reacting strictly to discrete attitude control actions.
 * - Articulated A-frame landing gear with telescoping hydraulic dampers and footpads.
 * - Real-time contact sensor emissive illumination directly driven by Box2D physical sensors.
 */

import * as THREE from 'three';
import type { SimulationSnapshotPayload } from '../types/protocol';
import { isPropulsionCutoff, mapSimulationTo3DPosition } from './coordinateMapping';

export interface BoosterComponents {
  root: THREE.Group;
  gimbalGroup: THREE.Group;
  mainPlumeGroup: THREE.Group;
  mainPlumeMesh: THREE.Mesh;
  mainPlumeCore: THREE.Mesh;
  plumeLight: THREE.PointLight;
  rcsLeftMesh: THREE.Mesh;
  rcsRightMesh: THREE.Mesh;
  leftGridFin: THREE.Group;
  rightGridFin: THREE.Group;
  leftFootpadMesh: THREE.Mesh;
  rightFootpadMesh: THREE.Mesh;
  leftFootpadMat: THREE.MeshStandardMaterial;
  rightFootpadMat: THREE.MeshStandardMaterial;
}

/**
 * Creates the complete procedural 3D booster model.
 */
export function createBoosterModel(quality: 'high' | 'low' = 'high'): BoosterComponents {
  const root = new THREE.Group();
  root.name = 'BoosterRoot';

  const segments = quality === 'high' ? 32 : 16;

  // ---------------------------------------------------------------------------
  // 1. Materials
  // ---------------------------------------------------------------------------
  const alloyWhiteMat = new THREE.MeshStandardMaterial({
    color: 0xF8FAFC,
    roughness: 0.35,
    metalness: 0.15,
  });

  const alloyDarkMat = new THREE.MeshStandardMaterial({
    color: 0x0F172A,
    roughness: 0.5,
    metalness: 0.3,
  });

  const carbonInterstageMat = new THREE.MeshStandardMaterial({
    color: 0x1E293B,
    roughness: 0.65,
    metalness: 0.5,
  });

  const titaniumFinMat = new THREE.MeshStandardMaterial({
    color: 0x475569,
    roughness: 0.4,
    metalness: 0.7,
  });

  const engineBellMat = new THREE.MeshStandardMaterial({
    color: 0x334155,
    roughness: 0.3,
    metalness: 0.8,
  });

  const legStrutMat = new THREE.MeshStandardMaterial({
    color: 0x64748B,
    roughness: 0.5,
    metalness: 0.4,
  });

  const leftFootpadMat = new THREE.MeshStandardMaterial({
    color: 0x475569,
    roughness: 0.4,
    metalness: 0.6,
  });

  const rightFootpadMat = new THREE.MeshStandardMaterial({
    color: 0x475569,
    roughness: 0.4,
    metalness: 0.6,
  });

  // ---------------------------------------------------------------------------
  // 2. Fuselage Cylindrical Core
  // ---------------------------------------------------------------------------
  // Box2D body width ~0.93u, height ~1.4u. Radius ~0.43u
  const bodyRadius = 0.42;
  const bodyHeight = 1.38;

  const coreGeom = new THREE.CylinderGeometry(bodyRadius, bodyRadius, bodyHeight, segments);
  const coreMesh = new THREE.Mesh(coreGeom, alloyWhiteMat);
  coreMesh.castShadow = quality === 'high';
  coreMesh.receiveShadow = quality === 'high';
  root.add(coreMesh);

  // External Avionics Raceway Conduits (cable trays down flanks)
  const racewayGeom = new THREE.BoxGeometry(0.04, bodyHeight * 0.85, 0.05);
  const leftRaceway = new THREE.Mesh(racewayGeom, alloyDarkMat);
  leftRaceway.position.set(-bodyRadius - 0.01, -0.05, 0);
  root.add(leftRaceway);

  const rightRaceway = new THREE.Mesh(racewayGeom, alloyDarkMat);
  rightRaceway.position.set(bodyRadius + 0.01, -0.05, 0);
  root.add(rightRaceway);

  // Carbon-Composite Interstage Ring
  const interstageGeom = new THREE.CylinderGeometry(
    bodyRadius + 0.005,
    bodyRadius + 0.005,
    0.22,
    segments
  );
  const interstageMesh = new THREE.Mesh(interstageGeom, carbonInterstageMat);
  interstageMesh.position.y = bodyHeight * 0.25;
  root.add(interstageMesh);

  // ---------------------------------------------------------------------------
  // 3. Aerodynamic Nose Fairing & Avionics Section
  // ---------------------------------------------------------------------------
  const noseHeight = 0.52;
  const noseGeom = new THREE.ConeGeometry(bodyRadius, noseHeight, segments);
  const noseMesh = new THREE.Mesh(noseGeom, alloyDarkMat);
  noseMesh.position.y = bodyHeight * 0.5 + noseHeight * 0.5;
  root.add(noseMesh);

  // Thermal Protection Nose Cap & Pitot Boom
  const capGeom = new THREE.SphereGeometry(0.06, 16, 16);
  const capMesh = new THREE.Mesh(capGeom, alloyDarkMat);
  capMesh.position.y = bodyHeight * 0.5 + noseHeight;
  root.add(capMesh);

  const pitotGeom = new THREE.CylinderGeometry(0.008, 0.008, 0.18, 8);
  const pitotMesh = new THREE.Mesh(pitotGeom, titaniumFinMat);
  pitotMesh.position.y = bodyHeight * 0.5 + noseHeight + 0.09;
  root.add(pitotMesh);

  // Forward Reaction Control System (RCS) Thruster Blocks
  const rcsBlockGeom = new THREE.BoxGeometry(0.06, 0.06, 0.06);
  const leftRcsBlock = new THREE.Mesh(rcsBlockGeom, alloyDarkMat);
  leftRcsBlock.position.set(-bodyRadius, bodyHeight * 0.45, 0);
  root.add(leftRcsBlock);

  const rightRcsBlock = new THREE.Mesh(rcsBlockGeom, alloyDarkMat);
  rightRcsBlock.position.set(bodyRadius, bodyHeight * 0.45, 0);
  root.add(rightRcsBlock);

  // ---------------------------------------------------------------------------
  // 4. Titanium Lattice Grid Fins (Aerodynamic Control)
  // ---------------------------------------------------------------------------
  const leftGridFin = createGridFinGroup(titaniumFinMat, 'left');
  leftGridFin.position.set(-bodyRadius - 0.02, bodyHeight * 0.35, 0);
  root.add(leftGridFin);

  const rightGridFin = createGridFinGroup(titaniumFinMat, 'right');
  rightGridFin.position.set(bodyRadius + 0.02, bodyHeight * 0.35, 0);
  root.add(rightGridFin);

  // Additional fore/aft decorative grid fins for 3D realism
  const fwdGridFin = createGridFinGroup(titaniumFinMat, 'fwd');
  fwdGridFin.position.set(0, bodyHeight * 0.35, bodyRadius + 0.02);
  fwdGridFin.rotation.y = Math.PI * 0.5;
  root.add(fwdGridFin);

  const aftGridFin = createGridFinGroup(titaniumFinMat, 'aft');
  aftGridFin.position.set(0, bodyHeight * 0.35, -bodyRadius - 0.02);
  aftGridFin.rotation.y = -Math.PI * 0.5;
  root.add(aftGridFin);

  // ---------------------------------------------------------------------------
  // 5. Gimbaled Engine Bay & Main Nozzle Bell
  // ---------------------------------------------------------------------------
  const boattailGeom = new THREE.CylinderGeometry(bodyRadius, bodyRadius * 0.8, 0.16, segments);
  const boattailMesh = new THREE.Mesh(boattailGeom, alloyDarkMat);
  boattailMesh.position.y = -bodyHeight * 0.5 - 0.08;
  root.add(boattailMesh);

  const gimbalGroup = new THREE.Group();
  gimbalGroup.position.set(0, -bodyHeight * 0.5 - 0.16, 0);
  root.add(gimbalGroup);

  // Engine Bell Nozzle
  // Calibrated so bell bottom sits at y = -1.05u, providing 0.033u clearance above footpads at y = -1.083u
  const bellGeom = new THREE.CylinderGeometry(0.12, 0.26, 0.20, segments, 1, true);
  const bellMesh = new THREE.Mesh(bellGeom, engineBellMat);
  bellMesh.position.y = -0.10;
  gimbalGroup.add(bellMesh);

  // Engine Throat Glow (Incandescent heat)
  const throatGeom = new THREE.CircleGeometry(0.11, 16);
  const throatMat = new THREE.MeshBasicMaterial({
    color: 0xFFAA00,
    side: THREE.DoubleSide,
  });
  const throatMesh = new THREE.Mesh(throatGeom, throatMat);
  throatMesh.rotation.x = Math.PI * 0.5;
  throatMesh.position.y = -0.01;
  gimbalGroup.add(throatMesh);

  // ---------------------------------------------------------------------------
  // 6. Main Engine Plume (Exhaust Supersonic Shock Envelope)
  // ---------------------------------------------------------------------------
  const mainPlumeGroup = new THREE.Group();
  mainPlumeGroup.position.set(0, -0.28, 0);
  gimbalGroup.add(mainPlumeGroup);

  // Outer Expanding Exhaust Flame Cone
  const plumeGeom = new THREE.ConeGeometry(0.36, 1.3, 16, 1, true);
  plumeGeom.translate(0, -0.65, 0);
  const plumeMat = new THREE.MeshBasicMaterial({
    color: 0xFF7A00,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const mainPlumeMesh = new THREE.Mesh(plumeGeom, plumeMat);
  mainPlumeGroup.add(mainPlumeMesh);

  // Inner Supersonic Diamond Core Cone
  const corePlumeGeom = new THREE.ConeGeometry(0.18, 0.75, 16, 1, true);
  corePlumeGeom.translate(0, -0.375, 0);
  const corePlumeMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const mainPlumeCore = new THREE.Mesh(corePlumeGeom, corePlumeMat);
  mainPlumeGroup.add(mainPlumeCore);

  // Dynamic Point Light at nozzle throat
  const plumeLight = new THREE.PointLight(0xFF9900, 0, 12, 1.2);
  plumeLight.position.set(0, -0.2, 0);
  mainPlumeGroup.add(plumeLight);

  // ---------------------------------------------------------------------------
  // 7. RCS Cold-Gas Reaction Thruster Plumes
  // ---------------------------------------------------------------------------
  const rcsGeom = new THREE.ConeGeometry(0.12, 0.35, 8);
  rcsGeom.translate(0, 0.175, 0);

  const rcsMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.75,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const rcsLeftMesh = new THREE.Mesh(rcsGeom, rcsMat);
  rcsLeftMesh.position.set(-bodyRadius - 0.05, bodyHeight * 0.45, 0);
  rcsLeftMesh.rotation.z = Math.PI * 0.5; // Fires to -X
  rcsLeftMesh.visible = false;
  root.add(rcsLeftMesh);

  const rcsRightMesh = new THREE.Mesh(rcsGeom, rcsMat);
  rcsRightMesh.position.set(bodyRadius + 0.05, bodyHeight * 0.45, 0);
  rcsRightMesh.rotation.z = -Math.PI * 0.5; // Fires to +X
  rcsRightMesh.visible = false;
  root.add(rcsRightMesh);

  // ---------------------------------------------------------------------------
  // 8. Articulated Landing Gear Assemblies
  // ---------------------------------------------------------------------------
  // Left Landing Gear Strut & Footpad
  const leftLegGroup = createLegAssembly(legStrutMat, leftFootpadMat, -1);
  leftLegGroup.position.set(-bodyRadius * 0.8, -bodyHeight * 0.35, 0);
  root.add(leftLegGroup);
  const leftFootpadMesh = leftLegGroup.getObjectByName('Footpad') as THREE.Mesh;

  // Right Landing Gear Strut & Footpad
  const rightLegGroup = createLegAssembly(legStrutMat, rightFootpadMat, 1);
  rightLegGroup.position.set(bodyRadius * 0.8, -bodyHeight * 0.35, 0);
  root.add(rightLegGroup);
  const rightFootpadMesh = rightLegGroup.getObjectByName('Footpad') as THREE.Mesh;

  // Fore / Aft landing gear struts for 3D realism
  const fwdLegGroup = createLegAssembly(legStrutMat, legStrutMat, 1);
  fwdLegGroup.position.set(0, -bodyHeight * 0.35, bodyRadius * 0.8);
  fwdLegGroup.rotation.y = Math.PI * 0.5;
  root.add(fwdLegGroup);

  const aftLegGroup = createLegAssembly(legStrutMat, legStrutMat, -1);
  aftLegGroup.position.set(0, -bodyHeight * 0.35, -bodyRadius * 0.8);
  aftLegGroup.rotation.y = Math.PI * 0.5;
  root.add(aftLegGroup);

  return {
    root,
    gimbalGroup,
    mainPlumeGroup,
    mainPlumeMesh,
    mainPlumeCore,
    plumeLight,
    rcsLeftMesh,
    rcsRightMesh,
    leftGridFin,
    rightGridFin,
    leftFootpadMesh,
    rightFootpadMesh,
    leftFootpadMat,
    rightFootpadMat,
  };
}

/**
 * Creates an articulated landing gear assembly with shock cylinder and footpad.
 */
function createLegAssembly(
  strutMat: THREE.Material,
  footpadMat: THREE.MeshStandardMaterial,
  sideSign: number
): THREE.Group {
  const group = new THREE.Group();

  // Primary Telescoping A-Frame Strut
  // Drops down to Y ~ -0.592 (calibrated Box2D leg reach), extends laterally ~0.58u
  const legLen = 0.82;
  const strutGeom = new THREE.CylinderGeometry(0.025, 0.025, legLen, 12);
  const strutMesh = new THREE.Mesh(strutGeom, strutMat);
  // Angle strut outward and downward
  strutMesh.position.set(sideSign * 0.28, -0.32, 0);
  strutMesh.rotation.z = -sideSign * 0.65;
  group.add(strutMesh);

  // Hydraulic Damper Piston
  const pistonGeom = new THREE.CylinderGeometry(0.018, 0.018, 0.55, 8);
  const pistonMesh = new THREE.Mesh(pistonGeom, strutMat);
  pistonMesh.position.set(sideSign * 0.15, -0.22, 0);
  pistonMesh.rotation.z = -sideSign * 0.42;
  group.add(pistonMesh);

  // Articulated Footpad (ground contact surface)
  const padGeom = new THREE.BoxGeometry(0.16, 0.04, 0.14);
  const footpadMesh = new THREE.Mesh(padGeom, footpadMat);
  footpadMesh.name = 'Footpad';
  footpadMesh.position.set(sideSign * 0.56, -0.58, 0);
  group.add(footpadMesh);

  return group;
}

/**
 * Creates a titanium lattice grid fin.
 */
function createGridFinGroup(finMat: THREE.Material, _label: string): THREE.Group {
  const finGroup = new THREE.Group();

  // Lattice border
  const borderGeom = new THREE.BoxGeometry(0.18, 0.12, 0.02);
  const borderMesh = new THREE.Mesh(borderGeom, finMat);
  borderMesh.position.x = 0.09;
  finGroup.add(borderMesh);

  // Internal cross rib
  const ribGeom = new THREE.BoxGeometry(0.14, 0.015, 0.018);
  const ribMesh = new THREE.Mesh(ribGeom, finMat);
  ribMesh.position.x = 0.09;
  finGroup.add(ribMesh);

  return finGroup;
}

/**
 * Updates booster model animation and actuator telemetry in real time.
 */
export function updateBoosterModel(
  booster: BoosterComponents,
  snap: SimulationSnapshotPayload | null,
  quality: 'high' | 'low' = 'high'
): void {
  if (!snap) {
    booster.mainPlumeGroup.visible = false;
    booster.rcsLeftMesh.visible = false;
    booster.rcsRightMesh.visible = false;
    booster.plumeLight.intensity = 0;
    return;
  }

  const k = snap.kinematics;
  const p = snap.propulsion;
  const g = snap.landing_gear;
  const l = snap.lifecycle;

  // 1. Position and Rotation
  // Maps authoritative Box2D state (posX, altitude) into Three.js coordinates,
  // applying the visual footpad contact offset so deployed footpads touch pad surface at altitude = 0.
  const pos = mapSimulationTo3DPosition(k.pos_x, k.altitude, true);
  const safeAngle = Number.isFinite(k.angle) ? k.angle : 0.0;

  booster.root.position.set(pos.x, pos.y, pos.z);
  booster.root.rotation.z = safeAngle;

  // 2. Titanium Grid Fins (Deflect subtly with angular velocity)
  // NOTE: Box2D does NOT model aerodynamic control surfaces. This deflection is a cosmetic
  // visual animation for visual feedback, not a physical simulation actuator.
  const finTilt = Number.isFinite(k.ang_vel) ? Math.max(-0.4, Math.min(0.4, k.ang_vel * 0.25)) : 0.0;
  booster.leftGridFin.rotation.z = finTilt;
  booster.rightGridFin.rotation.z = finTilt;

  // 3. Engine Nozzle Gimbaling
  // NOTE: Box2D LunarLander does NOT model engine gimbaling (it uses pure vertical thrust + RCS).
  // This nozzle deflection is a cosmetic visual animation indicating lateral velocity counter-steering.
  const gimbalAngle = Number.isFinite(k.vel_x) ? Math.max(-0.25, Math.min(0.25, -k.vel_x * 0.12)) : 0.0;
  booster.gimbalGroup.rotation.z = gimbalAngle;

  // 4. Main Engine Plume (Exhaust)
  const throttle = Number.isFinite(p.throttle) ? p.throttle : 0.0;
  const isCutoff = isPropulsionCutoff(l.terminated, l.truncated, throttle);

  if (!isCutoff && (p.action === 2 || throttle > 0) && throttle > 0) {
    booster.mainPlumeGroup.visible = true;

    // Faint turbulence flicker
    const flicker = 1.0 + (Math.random() - 0.5) * 0.15;
    const effThrottle = throttle * flicker;

    booster.mainPlumeGroup.scale.set(
      Math.max(0.4, effThrottle),
      Math.max(0.35, effThrottle),
      Math.max(0.4, effThrottle)
    );

    if (quality === 'high') {
      booster.plumeLight.intensity = throttle * 4.5;
    } else {
      booster.plumeLight.intensity = throttle * 2.0;
    }
  } else {
    booster.mainPlumeGroup.visible = false;
    booster.plumeLight.intensity = 0;
  }

  // 5. Directional Cold-Gas RCS Thruster Plumes
  // Reacts to discrete actions (Action 1 = right thruster firing / CCW torque, Action 3 = left thruster firing / CW torque)
  if (!l.terminated && !l.truncated) {
    const rcsLeft = Number.isFinite(p.rcs_left) ? p.rcs_left : 0.0;
    const rcsRight = Number.isFinite(p.rcs_right) ? p.rcs_right : 0.0;

    // Port RCS (Left)
    if ((p.action === 1 || rcsLeft > 0) && rcsLeft > 0) {
      booster.rcsLeftMesh.visible = true;
      booster.rcsLeftMesh.scale.set(rcsLeft, rcsLeft, rcsLeft);
    } else {
      booster.rcsLeftMesh.visible = false;
    }

    // Starboard RCS (Right)
    if ((p.action === 3 || rcsRight > 0) && rcsRight > 0) {
      booster.rcsRightMesh.visible = true;
      booster.rcsRightMesh.scale.set(rcsRight, rcsRight, rcsRight);
    } else {
      booster.rcsRightMesh.visible = false;
    }
  } else {
    booster.rcsLeftMesh.visible = false;
    booster.rcsRightMesh.visible = false;
  }

  // 6. Landing Gear Physical Contact Sensors
  // NOTE: Green emissive illumination reflects raw Box2D planar leg ground contact
  // (legs[0].ground_contact and legs[1].ground_contact). It indicates mechanical ground touch,
  // NOT terminal landing success (which requires complete velocity latch and settling criteria).
  if (g.left_contact) {
    booster.leftFootpadMat.emissive.setHex(0x00E676);
    booster.leftFootpadMat.emissiveIntensity = 1.8;
  } else {
    booster.leftFootpadMat.emissive.setHex(0x000000);
    booster.leftFootpadMat.emissiveIntensity = 0.0;
  }

  if (g.right_contact) {
    booster.rightFootpadMat.emissive.setHex(0x00E676);
    booster.rightFootpadMat.emissiveIntensity = 1.8;
  } else {
    booster.rightFootpadMat.emissive.setHex(0x000000);
    booster.rightFootpadMat.emissiveIntensity = 0.0;
  }
}
