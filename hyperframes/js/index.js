import { buildHookTimeline } from "./scenes/hook.js";
import { buildBridgeTimeline } from "./scenes/bridge.js";
import { buildQuoteTimeline } from "./scenes/quote.js";
import { buildCtaTimeline } from "./scenes/cta.js";
function getReelData() {
    const el = document.getElementById("reel-data");
    if (!el)
        throw new Error("Missing #reel-data");
    return JSON.parse(el.textContent || "{}");
}
window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused: true });
const data = getReelData();
const sf = data.sceneFrames;
if (data.hook && sf.hook > 0) {
    buildHookTimeline(tl, 0, sf.hook, data);
}
if (data.bridge && sf.bridge > 0) {
    buildBridgeTimeline(tl, sf.hook, sf.bridge, data);
}
if (sf.quote > 0) {
    buildQuoteTimeline(tl, sf.hook + sf.bridge, sf.quote, data);
}
if (sf.cta > 0) {
    buildCtaTimeline(tl, sf.hook + sf.bridge + sf.quote, sf.cta, data);
}
window.__timelines["main"] = tl;
