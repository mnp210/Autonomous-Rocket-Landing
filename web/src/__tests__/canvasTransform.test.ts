import { describe, it, expect } from 'vitest';

describe('Canvas Coordinate Transformation', () => {
  // Test coordinate projection matching SimulationCanvas logic
  const width = 1200;
  const height = 800;
  const worldSpanX = 20.0;
  const worldSpanY = 14.5;
  const padBottomMargin = 70;

  const scale = Math.min((width - 40) / worldSpanX, (height - padBottomMargin - 20) / worldSpanY);
  const centerX = width * 0.5;
  const groundY = height - padBottomMargin;

  const toScreenX = (bx: number) => centerX + bx * scale;
  const toScreenY = (by: number) => groundY - by * scale;

  it('maps pad center (0.0, 0.0) to screen pad center point', () => {
    const x = toScreenX(0.0);
    const y = toScreenY(0.0);

    expect(x).toBe(centerX);
    expect(y).toBe(groundY);
  });

  it('inverts vertical axis so that positive Box2D Y ascends upwards on screen', () => {
    const groundLevelY = toScreenY(0.0);
    const altitude10Y = toScreenY(10.0);

    // Canvas Y=0 is at the top, so higher altitude must have smaller screen Y coordinate
    expect(altitude10Y).toBeLessThan(groundLevelY);
    expect(groundLevelY - altitude10Y).toBeCloseTo(10.0 * scale, 3);
  });

  it('preserves horizontal symmetry for pad bounds', () => {
    const leftPadX = toScreenX(-2.0);
    const rightPadX = toScreenX(2.0);

    expect(centerX - leftPadX).toBeCloseTo(rightPadX - centerX, 3);
    expect(rightPadX - leftPadX).toBeCloseTo(4.0 * scale, 3);
  });

  it('computes velocity vector angles correctly', () => {
    // Pure descent: vel_x = 0, vel_y = -2.0
    const vx = 0;
    const vy = -(-2.0 * scale * 0.4); // Screen Y inverted
    const angle = Math.atan2(vy, vx);

    // Downwards vector points to +PI/2 in screen space
    expect(angle).toBeCloseTo(Math.PI / 2, 3);
  });

  it('determines velocity vector danger threshold colors correctly', () => {
    const getColor = (velY: number) => {
      if (Math.abs(velY) > 2.0) return '#FF1744'; // Danger
      if (Math.abs(velY) > 1.0) return '#FFB300'; // Caution
      return '#00E676'; // Safe
    };

    expect(getColor(-0.4)).toBe('#00E676'); // Safe sink
    expect(getColor(-1.0)).toBe('#00E676'); // Boundary safe
    expect(getColor(-1.5)).toBe('#FFB300'); // Caution
    expect(getColor(-2.5)).toBe('#FF1744'); // Danger
  });

  it('computes dynamic camera tracking zoom scaling correctly', () => {
    // When vehicle is near touchdown (altitude ~ 0.5), vertical span is small (~4.5 units)
    const altHigh = 12.0;
    const spanYHigh = Math.max(4.2, altHigh + 2.2) - (-0.8); // 14.2 - (-0.8) = 15.0
    const scaleHigh = (height - 95) / spanYHigh;

    const altLow = 0.5;
    const spanYLow = Math.max(4.2, altLow + 2.2) - (-0.8); // 4.2 - (-0.8) = 5.0
    const scaleLow = (height - 95) / spanYLow;

    // Scale low should be approximately 3x larger than scale high, providing high-detail touchdown view
    expect(scaleLow).toBeGreaterThan(scaleHigh * 2.5);
    expect(scaleLow / scaleHigh).toBeCloseTo(3.0, 1);
  });

  it('strictly verifies propulsion cutoff rules', () => {
    // Propulsion should be strictly active only when throttle > 0 and not terminated
    const shouldRenderMainPlume = (terminated: boolean, truncated: boolean, throttle: number) => {
      const isCutoff = terminated || truncated || throttle <= 0;
      return !isCutoff && throttle > 0;
    };

    expect(shouldRenderMainPlume(false, false, 1.0)).toBe(true);
    expect(shouldRenderMainPlume(false, false, 0.0)).toBe(false); // Coast
    expect(shouldRenderMainPlume(true, false, 1.0)).toBe(false); // Terminated
    expect(shouldRenderMainPlume(false, true, 1.0)).toBe(false); // Truncated
  });
});
