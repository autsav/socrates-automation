import { describe, it, expect } from "vitest";
import { getGrade, MOOD_GRADES } from "../js/lib/getGrade";

describe("getGrade", () => {
  it("returns a known grade for every mood", () => {
    const moods = Object.keys(MOOD_GRADES) as string[];
    for (const mood of moods) {
      const grade = getGrade(mood);
      expect(grade).toBeDefined();
      expect(typeof grade.filter).toBe("string");
      expect(grade.vignette).toBeGreaterThanOrEqual(0);
      expect(grade.vignette).toBeLessThanOrEqual(1);
    }
  });

  it("returns default grade for unknown mood", () => {
    const grade = getGrade("nonexistent_mood");
    expect(grade.filter).toBe("contrast(1.08) saturate(1.1)");
    expect(grade.vignette).toBe(0.5);
  });

  it("returns default grade for undefined mood", () => {
    const grade = getGrade(undefined);
    expect(grade.filter).toBe("contrast(1.08) saturate(1.1)");
    expect(grade.vignette).toBe(0.5);
  });

  it("dark_philosophical has expected filter", () => {
    const grade = getGrade("dark_philosophical");
    expect(grade.filter).toContain("contrast");
    expect(grade.vignette).toBe(0.55);
  });
});
