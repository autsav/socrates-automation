import { animateWords } from "../lib/animateWords.js";

export function buildQuoteTimeline(
  tl: gsap.core.Timeline,
  startSec: number,
  durationSec: number,
  data: { quote: string; attribution?: string; wordTimes?: Record<string, Array<{ w: string; start: number; end: number; cls?: string }>> },
): void {
  const container = document.getElementById("quote-text");
  if (!container) return;
  const words = data.wordTimes?.quote ?? [];
  animateWords(tl, container, words, startSec);

  const attr = document.getElementById("quote-attribution");
  if (attr) {
    tl.fromTo(
      attr,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" },
      startSec + 0.8,
    );
  }
}
