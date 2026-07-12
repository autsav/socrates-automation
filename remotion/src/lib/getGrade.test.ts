import { describe, it, expect } from "vitest";
import { getGrade } from "../styles/theme";

describe("getGrade", () => {
  it("returns a grade for a known mood", () => {
    const g = getGrade("dark_philosophical");
    expect(typeof g.filter).toBe("string");
    expect(g.vignette).toBeGreaterThan(0);
  });
  it("falls back to a default grade for unknown moods", () => {
    const g = getGrade("nonsense");
    expect(g.filter).toContain("contrast");
  });
});
