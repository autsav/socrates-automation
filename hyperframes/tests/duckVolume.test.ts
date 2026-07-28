import { describe, it, expect } from "vitest";
import { duckVolume } from "../js/lib/duckVolume";

const spans = [{ start: 30, end: 90 }];

describe("duckVolume", () => {
  it("returns the ducked gain inside a VO span", () => {
    expect(duckVolume(60, spans)).toBeCloseTo(0.12, 5);
  });

  it("returns the base gain far outside any span", () => {
    expect(duckVolume(200, spans)).toBeCloseTo(0.32, 5);
  });

  it("ramps down before a span starts", () => {
    const v = duckVolume(27, spans); // 3 frames into a 6-frame pre-ramp
    expect(v).toBeLessThan(0.32);
    expect(v).toBeGreaterThan(0.12);
  });

  it("handles no spans (always base)", () => {
    expect(duckVolume(50, [])).toBeCloseTo(0.32, 5);
  });
});
