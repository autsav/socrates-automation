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

/** Parse a countup target: integer ≤ 9999 (strip punctuation), else null. */
export function countupTarget(word: string): number | null {
  const m = word.replace(/[^\d]/g, "");
  if (!m) return null;
  const n = parseInt(m, 10);
  return Number.isFinite(n) && n <= 9999 ? n : null;
}
