import { buildHookTimeline } from "./scenes/hook.js";
import { buildBridgeTimeline } from "./scenes/bridge.js";
import { buildQuoteTimeline } from "./scenes/quote.js";
import { buildCtaTimeline } from "./scenes/cta.js";
import { buildParticleField } from "./effects/particleField.js";
import { buildGradientBg } from "./effects/gradientBg.js";
import { buildColorGrade } from "./effects/colorGrade.js";
import { buildFilmGrade } from "./effects/filmGrade.js";
import { buildPulsingBg } from "./effects/pulsingBg.js";
import { buildGlitchText } from "./effects/glitchText.js";
import { pickEmphasisIndex } from "./lib/emphasis.js";

declare global {
  interface Window {
    __timelines: Record<string, gsap.core.Timeline>;
  }
}

interface ReelData {
  hook?: string;
  quote: string;
  attribution?: string;
  cta: string;
  bridge?: string;
  mood: string;
  duration: number;
  fps: number;
  animSeed?: number;
  sceneFrames: {
    total: number;
    hook: number;
    bridge: number;
    quote: number;
    cta: number;
  };
  voices?: Record<string, string>;
  wordTimes?: Record<string, Array<{ w: string; start: number; end: number; cls?: string }>>;
  music?: string;
  silenceDropSec?: number;
  beats?: number[];
}

function getReelData(): ReelData {
  const el = document.getElementById("reel-data");
  if (!el) throw new Error("Missing #reel-data");
  return JSON.parse(el.textContent || "{}") as ReelData;
}

window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused: true });
const data = getReelData();
const sf = data.sceneFrames;
const totalDur = sf.total;

// ── Tier 2 effects (background + atmosphere) ──────────────────────────────
buildGradientBg(tl, totalDur);
buildPulsingBg(tl, totalDur);
buildParticleField(tl, totalDur, data.animSeed);
buildColorGrade(tl, totalDur, data.mood);
buildFilmGrade(tl, totalDur);

// ── Scene timelines ────────────────────────────────────────────────────────
if (data.hook && sf.hook > 0) {
  buildHookTimeline(tl, 0, sf.hook, data);
  // Glitch on the most emphasized hook word (if we have word times)
  const hookWords = data.wordTimes?.hook?.map((w) => w.w) || [];
  if (hookWords.length > 0) {
    const emphasisIdx = pickEmphasisIndex(hookWords);
    buildGlitchText(tl, 0, sf.hook, emphasisIdx, data.hook, data.animSeed);
  }
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
