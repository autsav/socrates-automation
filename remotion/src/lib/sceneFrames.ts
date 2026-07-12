export interface SceneFrames {
  total: number;
  hook: number;
  quote: number;
  cta: number;
}

/**
 * Frames per scene. When voiceover durations (seconds) are known, each scene is
 * sized to fit its narration + breathing room (so no VO is clipped); otherwise
 * falls back to fixed budgets derived from the total duration.
 */
export function sceneFrames(
  durationSec: number,
  fps: number,
  voiceDurations?: { hook?: number; quote?: number; cta?: number }
): SceneFrames {
  const vd = voiceDurations;
  if (vd && (vd.hook || vd.quote || vd.cta)) {
    const PAD = 0.6; // seconds after each VO
    const MIN = { hook: 2.5, quote: 3.0, cta: 2.0 };
    const secs = (d: number | undefined, min: number) => Math.max(min, (d ?? 0) + PAD);
    const hook = Math.round(secs(vd.hook, MIN.hook) * fps);
    const quote = Math.round(secs(vd.quote, MIN.quote) * fps);
    const cta = Math.round(secs(vd.cta, MIN.cta) * fps);
    return { total: hook + quote + cta, hook, quote, cta };
  }
  const total = Math.round(durationSec * fps);
  const hook = Math.min(Math.round(3.5 * fps), Math.round(total * 0.34));
  const cta = Math.min(Math.round(2.5 * fps), Math.round(total * 0.26));
  const quote = Math.max(total - hook - cta, Math.round(2 * fps));
  return { total: hook + quote + cta, hook, quote, cta };
}
