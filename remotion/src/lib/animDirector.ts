/** Deterministic per-word effect assignment (spec 3). Code is the director:
 *  class rules pick the technique, the seed varies flavor between reels. */
export type WordFx = "pop" | "pop2" | "shake" | "glowpop" | "countup" | "plain";

export function effectFor(
  cls: string | undefined,
  index: number,
  seed: number
): WordFx {
  switch (cls) {
    case "num":
      return "countup";
    case "neg":
      return "shake";
    case "power":
      return "glowpop";
    case "stress":
      return (seed + index) % 2 === 0 ? "pop" : "pop2";
    default:
      return "plain";
  }
}

/** Parse a countup target: a single plain digit run (optionally followed by
 *  trailing punctuation) that is ≤ 9999, else null. Words with embedded
 *  separators (e.g. "1,000") are rejected — AnimatedText's countup only
 *  animates the first digit group, so a comma number would flash transient
 *  garbage mid-roll. Nulls fall back to the "pop" effect. */
export function countupTarget(word: string): number | null {
  if (!/^\d+\W*$/.test(word)) return null;
  const m = word.replace(/[^\d]/g, "");
  if (!m) return null;
  const n = parseInt(m, 10);
  return Number.isFinite(n) && n <= 9999 ? n : null;
}
