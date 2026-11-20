/**
 * 3D Spaceport Facility & Environmental Scene.
 *
 * Constructs the procedural 3D aerospace spaceport:
 * - High-detail landing pad with concrete foundation, perimeter hazard chevrons,
 *   concentric touchdown rings, center reticle, and flashing boundary beacons.
 * - Surrounding spaceport infrastructure: umbilical launch tower, cryogenic propellant tanks,
 *   and lightning protection masts.
 * - Multi-layer terrain mesh with realistic topological elevation.
 * - Visual descent corridor, ground projection reticle, and estimated touchdown marker.
 * - Dynamic 3D velocity vector arrow color-coded by sink rate danger threshold.
 * - Atmospheric lighting, soft directional sunlight, and twilight celestial sky.
 */

import * as THREE from 'three';
import type { SessionReadyPayload, SimulationSnapshotPayload } from '../types/protocol';
import {
  computeEstimatedTouchdown,
  computeVelocityVector,
  BOOSTER_FOOTPAD_OFFSET,
} from './coordinateMapping';

export interface SpaceportSceneComponents {
  scene: THREE.Scene;
  padGroup: THREE.Group;
  terrainMesh: THREE.Mesh;
  beacons: THREE.Mesh[];
  descentCorridor: THREE.LineSegments;
  groundShadowReticle: THREE.Group;
  touchdownMarker: THREE.Group;
  velocityArrow: THREE.ArrowHelper;
  dirLight: THREE.DirectionalLight;
  hemiLight: THREE.HemisphereLight;
}

/**
 * Creates the complete procedural 3D spaceport scene and environment.
 */
export function createSpaceportScene(
  sessionReady: SessionReadyPayload | null,
  quality: 'high' | 'low' = 'high'
): SpaceportSceneComponents {
  const scene = new THREE.Scene();
  scene.name = 'SpaceportScene';

  // Atmospheric twilight fog
  scene.fog = new THREE.FogExp2(0x080D16, 0.015);
  scene.background = new THREE.Color(0x06090F);

  // ---------------------------------------------------------------------------
  // 1. Lighting Setup
  // ---------------------------------------------------------------------------
  // Ambient Hemispheric Light (Sky twilight to ground dark blue)
  const hemiLight = new THREE.HemisphereLight(0x3B4E68, 0x0C121D, 1.1);
  scene.add(hemiLight);

  // Key Directional Sun Light (Elevated low-angle aerospace lighting)
  const dirLight = new THREE.DirectionalLight(0xFFF5E6, 1.8);
  dirLight.position.set(10, 22, 14);

  if (quality === 'high') {
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    dirLight.shadow.camera.near = 1.0;
    dirLight.shadow.camera.far = 45;
    dirLight.shadow.camera.left = -14;
    dirLight.shadow.camera.right = 14;
    dirLight.shadow.camera.top = 18;
    dirLight.shadow.camera.bottom = -4;
    dirLight.shadow.bias = -0.001;
  }
  scene.add(dirLight);

  // Soft Fill Light from opposite quadrant
  const fillLight = new THREE.DirectionalLight(0x00F0FF, 0.4);
  fillLight.position.set(-12, 8, -8);
  scene.add(fillLight);

  // ---------------------------------------------------------------------------
  // 2. Starfield & Celestial Backdrop
  // ---------------------------------------------------------------------------
  const starCount = quality === 'high' ? 350 : 150;
  const starGeom = new THREE.BufferGeometry();
  const starPositions = new Float32Array(starCount * 3);
  for (let i = 0; i < starCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(Math.random() * 0.95 + 0.05); // Upper hemisphere
    const r = 50 + Math.random() * 20;
    starPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    starPositions[i * 3 + 1] = r * Math.cos(phi);
    starPositions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
  }
  starGeom.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
  const starMat = new THREE.PointsMaterial({
    color: 0xE2E8F0,
    size: 0.8,
    transparent: true,
    opacity: 0.65,
  });
  const starPoints = new THREE.Points(starGeom, starMat);
  scene.add(starPoints);

  // ---------------------------------------------------------------------------
  // 3. Primary Landing Pad (Helipad)
  // ---------------------------------------------------------------------------
  const padGroup = new THREE.Group();
  padGroup.name = 'LandingPad';
  scene.add(padGroup);

  // Helipad bounds: width ~4.0 units (radius 2.0u)
  const padRadius = sessionReady
    ? Math.abs(sessionReady.helipad_bounds[1] - sessionReady.helipad_bounds[0]) * 0.5
    : 2.0;

  // Concrete Foundation Block (Top surface rests exactly at Y = 0.0)
  const foundationThickness = 0.4;
  const padGeom = new THREE.CylinderGeometry(
    padRadius * 1.15,
    padRadius * 1.25,
    foundationThickness,
    32
  );
  padGeom.translate(0, -foundationThickness * 0.5, 0);

  const padConcreteMat = new THREE.MeshStandardMaterial({
    color: 0x1E293B,
    roughness: 0.85,
    metalness: 0.15,
  });
  const padMesh = new THREE.Mesh(padGeom, padConcreteMat);
  padMesh.receiveShadow = quality === 'high';
  padGroup.add(padMesh);

  // Pad Surface Plating
  const plateGeom = new THREE.CircleGeometry(padRadius * 1.12, 32);
  plateGeom.rotateX(-Math.PI * 0.5);
  plateGeom.translate(0, 0.005, 0);
  const plateMat = new THREE.MeshStandardMaterial({
    color: 0x131B26,
    roughness: 0.7,
    metalness: 0.3,
  });
  const plateMesh = new THREE.Mesh(plateGeom, plateMat);
  plateMesh.receiveShadow = quality === 'high';
  padGroup.add(plateMesh);

  // Perimeter Hazard Stripe Border (Procedural canvas texture)
  const hazardTexture = createHazardStripeTexture();
  const hazardGeom = new THREE.RingGeometry(padRadius * 0.98, padRadius * 1.1, 32);
  hazardGeom.rotateX(-Math.PI * 0.5);
  hazardGeom.translate(0, 0.008, 0);
  const hazardMat = new THREE.MeshBasicMaterial({
    map: hazardTexture,
    side: THREE.DoubleSide,
  });
  const hazardMesh = new THREE.Mesh(hazardGeom, hazardMat);
  padGroup.add(hazardMesh);

  // Target Concentric Rings (R=2.0u and R=1.0u)
  const outerRingGeom = new THREE.RingGeometry(padRadius * 0.94, padRadius * 0.96, 32);
  outerRingGeom.rotateX(-Math.PI * 0.5);
  outerRingGeom.translate(0, 0.009, 0);
  const ringCyanMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.7,
  });
  const outerRingMesh = new THREE.Mesh(outerRingGeom, ringCyanMat);
  padGroup.add(outerRingMesh);

  const innerRingGeom = new THREE.RingGeometry(padRadius * 0.48, padRadius * 0.50, 32);
  innerRingGeom.rotateX(-Math.PI * 0.5);
  innerRingGeom.translate(0, 0.009, 0);
  const innerRingMesh = new THREE.Mesh(innerRingGeom, ringCyanMat);
  padGroup.add(innerRingMesh);

  // Center Touchdown Crosshair '+'
  const crosshairGeom = new THREE.PlaneGeometry(0.8, 0.06);
  crosshairGeom.rotateX(-Math.PI * 0.5);
  crosshairGeom.translate(0, 0.01, 0);
  const crosshairMat = new THREE.MeshBasicMaterial({ color: 0x00F0FF });
  const crosshair1 = new THREE.Mesh(crosshairGeom, crosshairMat);
  padGroup.add(crosshair1);

  const crosshair2 = crosshair1.clone();
  crosshair2.rotation.y = Math.PI * 0.5;
  padGroup.add(crosshair2);

  // Corner Boundary Strobe Beacons
  const beacons: THREE.Mesh[] = [];
  const beaconOffsets = [
    [-padRadius * 1.05, 0],
    [padRadius * 1.05, 0],
    [0, -padRadius * 1.05],
    [0, padRadius * 1.05],
  ];

  beaconOffsets.forEach(([bx, bz]) => {
    const bPostGeom = new THREE.CylinderGeometry(0.04, 0.04, 0.25, 8);
    bPostGeom.translate(0, 0.125, 0);
    const bPostMesh = new THREE.Mesh(bPostGeom, padConcreteMat);
    bPostMesh.position.set(bx, 0, bz);
    padGroup.add(bPostMesh);

    const bBulbGeom = new THREE.SphereGeometry(0.06, 12, 12);
    const bBulbMat = new THREE.MeshBasicMaterial({ color: 0x00E676 });
    const bBulbMesh = new THREE.Mesh(bBulbGeom, bBulbMat);
    bBulbMesh.position.set(bx, 0.28, bz);
    padGroup.add(bBulbMesh);
    beacons.push(bBulbMesh);
  });

  // ---------------------------------------------------------------------------
  // 4. Surrounding Spaceport Structures & Launch Infrastructure
  // ---------------------------------------------------------------------------
  // Umbilical Service Tower (in background at X = -5.0, Z = -4.5)
  const towerGroup = createServiceTower(padConcreteMat);
  towerGroup.position.set(-4.8, 0, -4.5);
  towerGroup.castShadow = quality === 'high';
  scene.add(towerGroup);

  // Cryogenic Propellant Tanks (at X = 5.2, Z = -4.2)
  const tankFarm = createPropellantTankFarm();
  tankFarm.position.set(5.2, 0, -4.2);
  scene.add(tankFarm);

  // Lightning Protection Masts around perimeter
  const mast1 = createLightningMast();
  mast1.position.set(-6.5, 0, 4.0);
  scene.add(mast1);

  const mast2 = createLightningMast();
  mast2.position.set(6.5, 0, 4.0);
  scene.add(mast2);

  // ---------------------------------------------------------------------------
  // 5. Terrain Ground Surface
  // ---------------------------------------------------------------------------
  const terrainMesh = createSpaceportTerrain(sessionReady, quality);
  scene.add(terrainMesh);

  // ---------------------------------------------------------------------------
  // 6. Descent Corridor & Glideslope Guide Beams
  // ---------------------------------------------------------------------------
  const descentCorridor = createDescentCorridorGuides(padRadius);
  scene.add(descentCorridor);

  // ---------------------------------------------------------------------------
  // 7. Ground Projection Reticle & Estimated Touchdown Marker
  // ---------------------------------------------------------------------------
  const groundShadowReticle = createGroundShadowReticle();
  scene.add(groundShadowReticle);

  const touchdownMarker = createTouchdownMarker();
  scene.add(touchdownMarker);

  // ---------------------------------------------------------------------------
  // 8. 3D Velocity Vector Arrow
  // ---------------------------------------------------------------------------
  const velocityArrow = new THREE.ArrowHelper(
    new THREE.Vector3(0, -1, 0),
    new THREE.Vector3(0, 0, 0),
    1.0,
    0x00E676,
    0.3,
    0.15
  );
  scene.add(velocityArrow);

  return {
    scene,
    padGroup,
    terrainMesh,
    beacons,
    descentCorridor,
    groundShadowReticle,
    touchdownMarker,
    velocityArrow,
    dirLight,
    hemiLight,
  };
}

/**
 * Creates procedural yellow/black hazard striping texture for pad border.
 */
function createHazardStripeTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 32;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = '#FFB300';
  ctx.fillRect(0, 0, 256, 32);

  ctx.strokeStyle = '#000000';
  ctx.lineWidth = 14;
  for (let x = -32; x < 288; x += 28) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + 28, 32);
    ctx.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(8, 1);
  return texture;
}

/**
 * Creates a detailed spaceport umbilical launch service tower.
 */
function createServiceTower(mat: THREE.Material): THREE.Group {
  const tower = new THREE.Group();
  tower.name = 'ServiceTower';

  const towerHeight = 11.0;
  const towerWidth = 1.2;

  // 4 Corner Legs
  const legGeom = new THREE.BoxGeometry(0.08, towerHeight, 0.08);
  const legOffsets = [
    [-towerWidth * 0.5, -towerWidth * 0.5],
    [towerWidth * 0.5, -towerWidth * 0.5],
    [-towerWidth * 0.5, towerWidth * 0.5],
    [towerWidth * 0.5, towerWidth * 0.5],
  ];

  legOffsets.forEach(([lx, lz]) => {
    const leg = new THREE.Mesh(legGeom, mat);
    leg.position.set(lx, towerHeight * 0.5, lz);
    tower.add(leg);
  });

  // Cross Beams & Horizontal Girders
  for (let y = 1.0; y < towerHeight; y += 1.2) {
    const beamGeom = new THREE.BoxGeometry(towerWidth, 0.06, towerWidth);
    const beam = new THREE.Mesh(beamGeom, mat);
    beam.position.y = y;
    tower.add(beam);
  }

  // Lightning Rod at Tower Top
  const rodGeom = new THREE.CylinderGeometry(0.015, 0.03, 1.8, 8);
  const rodMat = new THREE.MeshBasicMaterial({ color: 0x94A3B8 });
  const rod = new THREE.Mesh(rodGeom, rodMat);
  rod.position.y = towerHeight + 0.9;
  tower.add(rod);

  // Red Aviation Warning Beacon at top
  const beaconGeom = new THREE.SphereGeometry(0.08, 8, 8);
  const beaconMat = new THREE.MeshBasicMaterial({ color: 0xFF1744 });
  const beacon = new THREE.Mesh(beaconGeom, beaconMat);
  beacon.position.y = towerHeight + 1.8;
  tower.add(beacon);

  return tower;
}

/**
 * Creates cryogenic vertical propellant storage tanks.
 */
function createPropellantTankFarm(): THREE.Group {
  const farm = new THREE.Group();
  farm.name = 'TankFarm';

  const tankMat = new THREE.MeshStandardMaterial({
    color: 0xF1F5F9,
    roughness: 0.3,
    metalness: 0.2,
  });

  // 2 Cryogenic Tanks
  [-0.9, 0.9].forEach((ox) => {
    const tankGeom = new THREE.CylinderGeometry(0.65, 0.65, 3.2, 24);
    const tank = new THREE.Mesh(tankGeom, tankMat);
    tank.position.set(ox, 1.6, 0);
    farm.add(tank);

    const domeGeom = new THREE.SphereGeometry(0.65, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.5);
    const dome = new THREE.Mesh(domeGeom, tankMat);
    dome.position.set(ox, 3.2, 0);
    farm.add(dome);
  });

  return farm;
}

/**
 * Creates perimeter lightning protection mast.
 */
function createLightningMast(): THREE.Group {
  const mast = new THREE.Group();
  const mastGeom = new THREE.CylinderGeometry(0.04, 0.12, 7.5, 12);
  const mastMat = new THREE.MeshStandardMaterial({
    color: 0x334155,
    roughness: 0.5,
    metalness: 0.7,
  });
  const mastMesh = new THREE.Mesh(mastGeom, mastMat);
  mastMesh.position.y = 3.75;
  mast.add(mastMesh);
  return mast;
}

/**
 * Creates the terrain mesh with depth variations.
 */
function createSpaceportTerrain(
  _sessionReady: SessionReadyPayload | null,
  quality: 'high' | 'low' = 'high'
): THREE.Mesh {
  const width = 36;
  const depth = 28;
  const segs = quality === 'high' ? 48 : 24;

  const geom = new THREE.PlaneGeometry(width, depth, segs, segs);
  geom.rotateX(-Math.PI * 0.5);

  const posAttr = geom.attributes.position;
  for (let i = 0; i < posAttr.count; i++) {
    const x = posAttr.getX(i);
    const z = posAttr.getZ(i);

    // Keep pad center zone (radius < 3.5u) flat at Y = -0.1
    const distToCenter = Math.sqrt(x * x + z * z);
    if (distToCenter < 3.2) {
      posAttr.setY(i, -0.1);
    } else {
      // Natural undulating dunes/crater elevation
      const elevation =
        Math.sin(x * 0.28) * 0.45 +
        Math.cos(z * 0.32) * 0.35 +
        Math.sin(x * 0.65 + z * 0.5) * 0.2 -
        0.25;
      posAttr.setY(i, elevation);
    }
  }

  geom.computeVertexNormals();

  const terrainMat = new THREE.MeshStandardMaterial({
    color: 0x0D1520,
    roughness: 0.95,
    metalness: 0.05,
    flatShading: quality === 'low',
  });

  const mesh = new THREE.Mesh(geom, terrainMat);
  mesh.position.y = 0.0;
  mesh.receiveShadow = quality === 'high';
  return mesh;
}

/**
 * Creates visual descent corridor guidelines.
 */
function createDescentCorridorGuides(padRadius: number): THREE.LineSegments {
  const points: THREE.Vector3[] = [];

  // 4 Guide Lines from high altitude (Y=14) down to pad radius
  const topY = 14.0;
  const topSpan = 4.5;
  const padSpan = padRadius * 0.95;

  points.push(new THREE.Vector3(-topSpan, topY, 0), new THREE.Vector3(-padSpan, 0, 0));
  points.push(new THREE.Vector3(topSpan, topY, 0), new THREE.Vector3(padSpan, 0, 0));

  // Gate Checkpoints at altitudes 2u, 5u, 10u
  [2, 5, 10].forEach((alt) => {
    const frac = alt / 14.0;
    const span = padSpan + (topSpan - padSpan) * frac;
    points.push(new THREE.Vector3(-span, alt, 0), new THREE.Vector3(span, alt, 0));
  });

  const geom = new THREE.BufferGeometry().setFromPoints(points);
  const mat = new THREE.LineBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.18,
  });

  return new THREE.LineSegments(geom, mat);
}

/**
 * Creates ground shadow reticle beneath the descending vehicle.
 */
function createGroundShadowReticle(): THREE.Group {
  const group = new THREE.Group();
  group.name = 'GroundShadowReticle';

  const ringGeom = new THREE.RingGeometry(0.42, 0.48, 32);
  ringGeom.rotateX(-Math.PI * 0.5);
  ringGeom.translate(0, 0.012, 0);

  const ringMat = new THREE.MeshBasicMaterial({
    color: 0x00F0FF,
    transparent: true,
    opacity: 0.55,
    side: THREE.DoubleSide,
  });

  const ring = new THREE.Mesh(ringGeom, ringMat);
  group.add(ring);

  // Vertical guideline from reticle to vehicle
  const lineGeom = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0.015, 0),
    new THREE.Vector3(0, 1.0, 0),
  ]);
  const lineMat = new THREE.LineDashedMaterial({
    color: 0x00F0FF,
    dashSize: 0.2,
    gapSize: 0.15,
    transparent: true,
    opacity: 0.35,
  });
  const line = new THREE.Line(lineGeom, lineMat);
  line.name = 'Guideline';
  group.add(line);

  return group;
}

/**
 * Creates projected touchdown marker.
 */
function createTouchdownMarker(): THREE.Group {
  const group = new THREE.Group();
  group.name = 'TouchdownMarker';

  const markerGeom = new THREE.CircleGeometry(0.24, 16);
  markerGeom.rotateX(-Math.PI * 0.5);
  markerGeom.translate(0, 0.015, 0);

  const markerMat = new THREE.MeshBasicMaterial({
    color: 0x00E676,
    side: THREE.DoubleSide,
  });

  const marker = new THREE.Mesh(markerGeom, markerMat);
  group.add(marker);
  group.visible = false;
  return group;
}

/**
 * Updates spaceport dynamic elements per animation frame.
 */
export function updateSpaceportScene(
  sceneComps: SpaceportSceneComponents,
  snap: SimulationSnapshotPayload | null
): void {
  // 1. Boundary Beacon Strobe pulsing
  const timeSec = Date.now() * 0.003;
  const beaconIntensity = 0.5 + 0.5 * Math.sin(timeSec * 5.0);
  sceneComps.beacons.forEach((b) => {
    (b.material as THREE.MeshBasicMaterial).color.setRGB(
      0.0,
      beaconIntensity * 0.9,
      beaconIntensity * 0.5
    );
  });

  if (!snap) {
    sceneComps.groundShadowReticle.visible = false;
    sceneComps.touchdownMarker.visible = false;
    sceneComps.velocityArrow.visible = false;
    return;
  }

  const k = snap.kinematics;
  const safePosX = Number.isFinite(k.pos_x) ? k.pos_x : 0.0;
  const safeAlt = Number.isFinite(k.altitude) ? Math.max(0.0, k.altitude) : 0.0;
  const safeVelX = Number.isFinite(k.vel_x) ? k.vel_x : 0.0;
  const safeVelY = Number.isFinite(k.vel_y) ? k.vel_y : 0.0;

  // 2. Ground Shadow Reticle
  sceneComps.groundShadowReticle.visible = true;
  sceneComps.groundShadowReticle.position.set(safePosX, 0.0, 0.0);

  // Update vertical guideline height to vehicle center of mass
  const guideline = sceneComps.groundShadowReticle.getObjectByName('Guideline') as THREE.Line;
  if (guideline) {
    guideline.scale.set(1, Math.max(0.01, safeAlt + BOOSTER_FOOTPAD_OFFSET), 1);
  }

  // 3. Projected Touchdown Intercept Point (Kinematic open-loop projection)
  const est = computeEstimatedTouchdown(safePosX, safeAlt, safeVelX, safeVelY);
  if (est && Number.isFinite(est.predX)) {
    sceneComps.touchdownMarker.visible = true;
    sceneComps.touchdownMarker.position.set(est.predX, 0.0, 0.0);
    const markerMat = (
      sceneComps.touchdownMarker.children[0] as THREE.Mesh
    ).material as THREE.MeshBasicMaterial;
    markerMat.color.setHex(est.isSafe ? 0x00E676 : 0xFFB300);
  } else {
    sceneComps.touchdownMarker.visible = false;
  }

  // 4. 3D Velocity Vector Arrow (Originates at booster center of mass)
  const vel = computeVelocityVector(safeVelX, safeVelY);
  if (vel.speed > 0.06) {
    sceneComps.velocityArrow.visible = true;
    sceneComps.velocityArrow.position.set(safePosX, safeAlt + BOOSTER_FOOTPAD_OFFSET, 0.0);

    const dir = new THREE.Vector3(safeVelX, safeVelY, 0).normalize();
    if (Number.isFinite(dir.x) && Number.isFinite(dir.y)) {
      sceneComps.velocityArrow.setDirection(dir);
      // Scale arrow length proportional to speed (max length 2.2u)
      const arrowLen = Math.min(2.2, Math.max(0.4, vel.speed * 0.45));
      sceneComps.velocityArrow.setLength(arrowLen, arrowLen * 0.28, arrowLen * 0.14);
      sceneComps.velocityArrow.setColor(new THREE.Color(vel.color));
    }
  } else {
    sceneComps.velocityArrow.visible = false;
  }
}
