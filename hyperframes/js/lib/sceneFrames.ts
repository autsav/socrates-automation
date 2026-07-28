export interface VoiceDurations {
  hook?: number;
  bridge?: number;
  quote?: number;
  cta?: number;
}

export interface SceneFrames {
  total: number;   // seconds
  hook: number;    // seconds
  bridge: number;  // seconds
  quote: number;   // seconds
  cta: number;     // seconds
}

const HOOK_GASP = 0.25;
const PAD = 0.2;
const MIN = { hook: 1.6, bridge: 2.5, quote: 3.0, cta: 1.8 };

function secs(d: number | undefined, min: number, extra = 0): number {
  return Math.max(min, (d ?? 0) + PAD + extra);
}

export function sceneFrames(
  durationSec: number,
  fps: number,
  voiceDurations?: VoiceDurations,
  hasBridge = false,
  hasHook = true,
): SceneFrames {
  const vd = voiceDurations;
  const bridgeOn = hasBridge || !!(vd && vd.bridge);

  if (vd && (vd.hook || vd.bridge || vd.quote || vd.cta)) {
    const hook = hasHook ? secs(vd.hook, MIN.hook, HOOK_GASP) : 0;
    const bridge = bridgeOn ? secs(vd.bridge, MIN.bridge) : 0;
    const quote = secs(vd.quote, MIN.quote);
    const cta = secs(vd.cta, MIN.cta);
    return {
      total: hook + bridge + quote + cta,
      hook, bridge, quote, cta,
    };
  }

  // No voice timings: distribute the nominal durationSec across scenes.
  // Ported from Remotion frame logic, converted to seconds.
  const hookFrac = bridgeOn ? 0.3 : 0.34;
  const ctaFrac = bridgeOn ? 0.24 : 0.26;
  const hook = hasHook ? Math.min(3.5, durationSec * hookFrac) : 0;
  const bridge = bridgeOn ? 2.5 : 0;
  const cta = Math.min(2.5, durationSec * ctaFrac);
  const quote = Math.max(durationSec - hook - bridge - cta, 2.0);
  return {
    total: hook + bridge + quote + cta,
    hook, bridge, quote, cta,
  };
}
