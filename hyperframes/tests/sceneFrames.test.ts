import { describe, it, expect } from "vitest";
import { sceneFrames } from "../js/lib/sceneFrames";

describe("sceneFrames (seconds)", () => {
  it("returns seconds, not frames", () => {
    const r = sceneFrames(10, 30, undefined, false, true);
    expect(r.total).toBe(10);
    expect(r.hook).toBeGreaterThan(0);
    expect(r.cta).toBeGreaterThan(0);
  });

  it("respects MIN floors (in seconds)", () => {
    const r = sceneFrames(3, 30, { hook: 0.1, quote: 0.1, cta: 0.1 }, false, true);
    expect(r.hook).toBeGreaterThanOrEqual(1.6);
    expect(r.quote).toBeGreaterThanOrEqual(3.0);
    expect(r.cta).toBeGreaterThanOrEqual(1.8);
  });

  it("matches Remotion frame output when multiplied by fps", () => {
    // Same inputs as the Remotion test's flagship case; assert round(sec*fps) == Remotion frames.
    const fps = 30;
    const r = sceneFrames(10, fps, { hook: 2.0, quote: 4.0, cta: 1.5 }, false, true);
    // hook = max(1.6, 2.0 + 0.2 + 0.25) = 2.45 -> round(2.45*30) = 74
    expect(Math.round(r.hook * fps)).toBe(74);
    // quote = max(3.0, 4.0 + 0.2) = 4.2 -> 126
    expect(Math.round(r.quote * fps)).toBe(126);
    // cta = max(1.8, 1.5 + 0.2) = 1.8 -> 54
    expect(Math.round(r.cta * fps)).toBe(54);
  });

  it("bridge=0 when hasBridge false and no bridge voice", () => {
    const r = sceneFrames(10, 30, { hook: 2, quote: 4, cta: 1.5 }, false, true);
    expect(r.bridge).toBe(0);
  });

  it("bridge floored at 2.5s when hasBridge true", () => {
    const r = sceneFrames(10, 30, { hook: 2, quote: 4, cta: 1.5 }, true, true);
    expect(r.bridge).toBeGreaterThanOrEqual(2.5);
  });

  it("hook=0 when hasHook false", () => {
    const r = sceneFrames(10, 30, { quote: 4, cta: 1.5 }, false, false);
    expect(r.hook).toBe(0);
  });
});
