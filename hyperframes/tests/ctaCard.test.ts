import { describe, it, expect, vi } from "vitest";

// Mock GSAP so string selectors don't blow up under Node-only Vitest.
vi.mock("gsap", async () => {
  const m = await import("./_gsap-mock");
  return { default: m.default };
});

import { ctaCard } from "../js/lib/ctaCard";

describe("ctaCard", () => {
  it("returns GSAP timeline with fade-in + fade-out", () => {
    const tl = ctaCard({
      copy: "Follow @socrates",
      url: "https://ig.com/socrates",
      durationSec: 3.0,
    });
    expect(tl).toBeDefined();
    // Entrance ends at 0.3, settle by 0.3, exit 3.0→3.2 → duration ≈ 3.2
    expect(tl.duration()).toBeCloseTo(3.2, 1);
  });

  it("works without URL", () => {
    const tl = ctaCard({ copy: "Follow", durationSec: 1.0 });
    expect(tl).toBeDefined();
  });

  it("fade-in visible label is set (relative timeline)", () => {
    const tl = ctaCard({ copy: "X", durationSec: 1.0 });
    expect(tl.labels?.["cta_visible"]).toBeDefined();
    // Relative: cta_visible at 0.3
    expect(tl.labels?.["cta_visible"]).toBe(0.3);
  });
});
