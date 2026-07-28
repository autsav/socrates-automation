import { animateWords } from "../lib/animateWords.js";
export function buildBridgeTimeline(tl, startSec, durationSec, data) {
    const container = document.getElementById("bridge-text");
    if (!container || !data.bridge)
        return;
    const words = data.wordTimes?.bridge ?? [];
    animateWords(tl, container, words, startSec);
}
