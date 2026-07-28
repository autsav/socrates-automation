import { animateWords } from "../lib/animateWords.js";

export function buildHookTimeline(
  tl: gsap.core.Timeline,
  startSec: number,
  durationSec: number,
  data: { hook?: string; wordTimes?: Record<string, Array<{ w: string; start: number; end: number; cls?: string }>> },
): void {
  const container = document.getElementById("hook-text");
  if (!container || !data.hook) return;
  const words = data.wordTimes?.hook ?? [];
  animateWords(tl, container, words, startSec);
}
