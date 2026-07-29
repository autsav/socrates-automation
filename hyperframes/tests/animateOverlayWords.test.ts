import { describe, it, expect, vi } from "vitest";

// Mock GSAP so string selectors don't blow up under Node-only Vitest.
vi.mock("gsap", async () => {
  const m = await import("./_gsap-mock");
  return { default: m.default };
});

import { animateOverlayWords } from "../js/lib/animateOverlayWords";

describe("animateOverlayWords", () => {
  it("returns GSAP timeline", () => {
    const tl = animateOverlayWords(
      [{ t: 0.42, w: "The" }, { t: 0.78, w: "unexamined" }],
      2.5,
    );
    expect(tl).toBeDefined();
    // Relative helper: last tween ends at 0.78 + 0.2 + 0.15 = 1.13
    expect(tl.duration()).toBeCloseTo(1.13, 1);
  });

  it("handles empty input", () => {
    const tl = animateOverlayWords([], 0);
    expect(tl.duration()).toBe(0);
  });

  it("adds a label per word", () => {
    const tl = animateOverlayWords(
      [{ t: 0.0, w: "A" }, { t: 1.0, w: "B" }],
      2.0,
    );
    expect(tl.labels?.["w_0"]).toBe(0);
    expect(tl.labels?.["w_1"]).toBe(1);
  });
});
