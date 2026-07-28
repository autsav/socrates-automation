import { animateWords } from "../lib/animateWords.js";
export function buildHookTimeline(tl, startSec, durationSec, data) {
    const container = document.getElementById("hook-text");
    if (!container || !data.hook)
        return;
    const words = data.wordTimes?.hook ?? [];
    animateWords(tl, container, words, startSec);
}
