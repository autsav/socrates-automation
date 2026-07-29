// Animate scene-relative word highlights (overlay captions).
//
// Each `WordTiming` carries its position WITHIN the scene (already offset by
// the orchestrator). The returned timeline starts from t=0 — the caller (Task
// 5 orchestrator) composes it at the scene's absolute time via
// `master.add(childTl, sceneAtSec)`.

import gsap from "gsap";

export interface WordTiming {
  /** Seconds from the start of the parent scene. */
  t: number;
  /** Word text (kept for future caption rendering; not used for animation). */
  w: string;
}

export function animateOverlayWords(
  sceneWords: WordTiming[],
  durationSec: number,
  sceneName: string,
): gsap.core.Timeline {
  const tl = gsap.timeline();
  sceneWords.forEach((word, idx) => {
    tl.addLabel(`w_${idx}`, word.t);
    tl.to(
      `#overlay-word-${sceneName}-${idx}`,
      { scale: 1.15, color: "#FFD700", duration: 0.2, ease: "power2.out" },
      word.t,
    );
    tl.to(
      `#overlay-word-${sceneName}-${idx}`,
      { scale: 1.0, color: "#FFFFFF", duration: 0.15, ease: "power2.in" },
      word.t + 0.2,
    );
  });
  // `durationSec` is the scene length (not used for tween placement) — kept
  // in the signature for Task-5 planning parity, ignored by the helper.
  void durationSec;
  return tl;
}
