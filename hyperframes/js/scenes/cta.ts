import { animateWords } from "../lib/animateWords.js";

export function buildCtaTimeline(
  tl: gsap.core.Timeline,
  startSec: number,
  durationSec: number,
  data: { cta: string; wordTimes?: Record<string, Array<{ w: string; start: number; end: number; cls?: string }>> },
): void {
  const container = document.getElementById("cta-text");
  if (!container) return;
  const words = data.wordTimes?.cta ?? [];
  animateWords(tl, container, words, startSec);
}
