import { describe, it, expect } from "vitest";
import { sceneFrames } from "./sceneFrames";

describe("sceneFrames", () => {
  it("sizes scenes to fit VO durations (no clipping) when provided", () => {
    const fps = 30;
    const s = sceneFrames(10.5, fps, { hook: 4.0, quote: 6.0, cta: 5.0 });
    expect(s.hook).toBeGreaterThanOrEqual(Math.round(4.0 * fps));
    expect(s.cta).toBeGreaterThanOrEqual(Math.round(5.0 * fps)); // was clipped at 2.5s before
    expect(s.total).toBe(s.hook + s.quote + s.cta);
  });

  it("enforces per-scene minimums when VO is short", () => {
    const fps = 30;
    const s = sceneFrames(10.5, fps, { quote: 0.5 });
    expect(s.hook).toBeGreaterThanOrEqual(Math.round(2.5 * fps));
    expect(s.quote).toBeGreaterThanOrEqual(Math.round(3.0 * fps));
  });

  it("falls back to fixed budgets without voiceDurations", () => {
    const fps = 30;
    const s = sceneFrames(10.5, fps);
    expect(s.total).toBe(s.hook + s.quote + s.cta);
    expect(s.hook).toBeLessThanOrEqual(Math.round(3.5 * fps));
  });
});
