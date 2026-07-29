import { describe, it, expect, vi } from "vitest";

// Mock GSAP so string selectors don't blow up under Node-only Vitest.
vi.mock("gsap", async () => {
  const m = await import("./_gsap-mock");
  return { default: m.default };
});

import { rpmHook } from "../js/lib/rpmHook";

describe("rpmHook", () => {
  it("returns GSAP timeline with entrance + exit", () => {
    const tl = rpmHook({ text: "Did you know?", durationSec: 1.5, style: "pop" });
    expect(tl).toBeDefined();
    // pop: 0→0.3 entrance, 0.3→0.5 settle, 1.5→1.7 exit → duration ≈ 1.7
    expect(tl.duration()).toBeGreaterThanOrEqual(1.5);
  });

  it("supports slide style", () => {
    const tl = rpmHook({ text: "Hi", durationSec: 1.0, style: "slide" });
    expect(tl).toBeDefined();
    // exit at 1.0 → 1.2
    expect(tl.duration()).toBeCloseTo(1.2, 1);
  });

  it("handles zero duration gracefully", () => {
    const tl = rpmHook({ text: "X", durationSec: 0, style: "pop" });
    expect(tl).toBeDefined();
  });

  it("pop style uses from() with scale (relative timeline)", () => {
    const tl = rpmHook({ text: "Test", durationSec: 1.0, style: "pop" });
    // Helper is relative: rpm_entrance label is at t=0
    expect(tl.labels?.["rpm_entrance"]).toBe(0);
  });
});
