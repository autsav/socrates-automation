export interface SceneFrames {
  total: number;
  hook: number;
  bridge: number;
  quote: number;
  cta: number;
}

/**
 * Frames per scene. When voiceover durations (seconds) are known, each scene is
 * sized to fit its narration + breathing room (so no VO is clipped); otherwise
 * falls back to fixed budgets derived from the total duration.
 *
 * The Bridge is an OPTIONAL 4th scene between Hook and Quote — it only takes
 * frames when `hasBridge` is true or `voiceDurations.bridge` is set; otherwise
 * `bridge` is 0 and the total is identical to the pre-Bridge 3-scene arc.
 */
export function sceneFrames(
  durationSec: number,
  fps: number,
  voiceDurations?: { hook?: number; bridge?: number; quote?: number; cta?: number },
  hasBridge = false,
  hasHook = true
): SceneFrames {
  const vd = voiceDurations;
  const bridgeOn = hasBridge || !!(vd && vd.bridge);
  if (vd && (vd.hook || vd.bridge || vd.quote || vd.cta)) {
    const PAD = 0.6;
    const MIN = { hook: 2.5, bridge: 2.5, quote: 3.0, cta: 2.0 };
    const secs = (d: number | undefined, min: number) => Math.max(min, (d ?? 0) + PAD);
    const hook = hasHook ? Math.round(secs(vd.hook, MIN.hook) * fps) : 0;
    const bridge = bridgeOn ? Math.round(secs(vd.bridge, MIN.bridge) * fps) : 0;
    const quote = Math.round(secs(vd.quote, MIN.quote) * fps);
    const cta = Math.round(secs(vd.cta, MIN.cta) * fps);
    return { total: hook + bridge + quote + cta, hook, bridge, quote, cta };
  }
  const total = Math.round(durationSec * fps);
  // When the Bridge is off, these fractions must match the original (pre-Bridge)
  // 3-scene budgets exactly — a bridge-less reel's Hook/CTA timing is unchanged.
  // When the Bridge is on, slightly smaller fractions carve out room for it.
  const hookFrac = bridgeOn ? 0.3 : 0.34;
  const ctaFrac = bridgeOn ? 0.24 : 0.26;
  const hook = hasHook ? Math.min(Math.round(3.5 * fps), Math.round(total * hookFrac)) : 0;
  const bridge = bridgeOn ? Math.round(2.5 * fps) : 0;
  const cta = Math.min(Math.round(2.5 * fps), Math.round(total * ctaFrac));
  const quote = Math.max(total - hook - bridge - cta, Math.round(2 * fps));
  return { total: hook + bridge + quote + cta, hook, bridge, quote, cta };
}
