import { describe, it, expect } from "vitest";
import { pickEmphasisIndex } from "../js/lib/emphasis";

describe("pickEmphasisIndex", () => {
  it("picks the last content word, skipping trailing punctuation", () => {
    const words = "The beginning of wisdom is the desire to learn.".split(/\s+/);
    // last word is "learn." -> index 8
    expect(pickEmphasisIndex(words)).toBe(words.length - 1);
  });

  it("skips a trailing stopword to reach a content word", () => {
    const words = ["Know", "thyself", "and", "the"];
    // "the" is a stopword -> fall back to "and"? no, "and" is a stopword too -> "thyself"
    expect(pickEmphasisIndex(words)).toBe(1);
  });

  it("picks the last content word, scanning back past trailing stopwords", () => {
    const words = ["Wisdom", "is", "the", "of"];
    // "of" and "the" are stopwords -> last content word scan lands on "Wisdom" (index 0).
    // The separate longest-word fallback (no content word at all) is covered below.
    expect(pickEmphasisIndex(words)).toBe(0);
  });

  it("handles a single word", () => {
    expect(pickEmphasisIndex(["Courage"])).toBe(0);
  });

  it("handles empty input without throwing", () => {
    expect(pickEmphasisIndex([])).toBe(0);
  });

  it("falls back to the longest word when every word is a stopword", () => {
    // No non-stopword content word exists, so the first loop finds nothing and
    // the longest-content-word fallback runs. Lengths: the=3, of=2, a=1 -> index 0.
    expect(pickEmphasisIndex(["the", "of", "a"])).toBe(0);
  });

  it("returns the last index when all words are punctuation-only", () => {
    // clean() strips everything -> no content word -> final words.length-1 fallback.
    expect(pickEmphasisIndex(["...", "!!!"])).toBe(1);
  });
});
