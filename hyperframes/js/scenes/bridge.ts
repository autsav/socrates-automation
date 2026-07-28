import { animateWords } from "../lib/animateWords.js";

export function buildBridgeTimeline(
  tl: gsap.core.Timeline,
  startSec: number,
  durationSec: number,
  data: { bridge?: string; wordTimes?: Record<string, Array<{ w: string; start: number; end: number; cls?: string }>> },
): void {
  const container = document.getElementById("bridge-text");
  if (!container || !data.bridge) return;
  const words = data.wordTimes?.bridge ?? [];
  animateWords(tl, container, words, startSec);
}
