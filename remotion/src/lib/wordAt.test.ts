import { describe, it, expect } from "vitest";
import { wordAt } from "./wordAt";

const words = [
  { w: "a", start: 0.0, end: 0.3 },
  { w: "b", start: 0.3, end: 0.6 },
  { w: "c", start: 0.6, end: 0.9 },
];

describe("wordAt", () => {
  it("is -1 before the first word", () => expect(wordAt(-0.1, words)).toBe(-1));
  it("returns the active word index", () => expect(wordAt(0.4, words)).toBe(1));
  it("stays on the last word after it ends", () => expect(wordAt(5, words)).toBe(2));
  it("empty words -> -1", () => expect(wordAt(1, [])).toBe(-1));
});
