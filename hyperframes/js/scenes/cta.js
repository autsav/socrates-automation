import { animateWords } from "../lib/animateWords.js";
export function buildCtaTimeline(tl, startSec, durationSec, data) {
    const container = document.getElementById("cta-text");
    if (!container)
        return;
    const words = data.wordTimes?.cta ?? [];
    animateWords(tl, container, words, startSec);
}
