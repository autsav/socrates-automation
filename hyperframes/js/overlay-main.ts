// hyperframes/js/overlay-main.ts
//
// Overlay orchestrator. Reads scene-relative word timings + RPM hooks + CTA
// from `<script id="overlay-data">` (rendered from overlay.html.j2) and
// composes them into a single master GSAP timeline.
//
// Architecture (Task 4 contract):
//   - animateOverlayWords / rpmHook / ctaCard return RELATIVE timelines.
//   - `atSec` is NOT in the helper spec — orchestrator composes each child
//     into master at the absolute time via `master.add(childTl, atSec)`.
//   - `master.duration(data.base_duration_sec)` pins the master length so
//     Task 6's Puppeteer renderer can drive frame capture deterministically.
//
// Browser bundle: `data` is JSON-parsed at runtime; we cast through `any` to
// avoid an extra type-validation layer at the JSON boundary.

import gsap from "gsap";
import { animateOverlayWords } from "./lib/animateOverlayWords";
import { rpmHook } from "./lib/rpmHook";
import { ctaCard } from "./lib/ctaCard";

const data = (JSON.parse(
  document.getElementById("overlay-data")!.textContent!,
) as unknown) as {
  scenes: Record<
    string,
    { words: { t: number; w: string }[]; start_sec: number; duration_sec: number }
  >;
  base_duration_sec: number;
  rpm_hooks?: { at_sec: number; text: string; duration_sec: number; style: "pop" | "slide" | "fade" }[];
  cta_copy?: string;
  cta_url?: string;
  cta_start_sec?: number;
  cta_duration_sec?: number;
};

const master = gsap.timeline();

// Per-scene word animations: each scene's words are already scene-relative
// (animateOverlayWords builds a relative timeline). The orchestrator
// positions the per-scene timeline at scene start_sec in master time.
for (const [sceneName, sceneData] of Object.entries(data.scenes)) {
  const tl = animateOverlayWords(sceneData.words, sceneData.duration_sec, sceneName);
  master.add(tl, sceneData.start_sec);
}

// RPM hooks (pop / slide / fade). Position each at hook.at_sec.
for (const hook of data.rpm_hooks || []) {
  const tl = rpmHook({
    text: hook.text,
    durationSec: hook.duration_sec,
    style: hook.style,
  });
  master.add(tl, hook.at_sec);
}

// CTA card. Only present when cta_copy is set (CTA scene is optional).
if (data.cta_copy && data.cta_start_sec !== undefined && data.cta_duration_sec !== undefined) {
  const tl = ctaCard({
    copy: data.cta_copy,
    url: data.cta_url,
    durationSec: data.cta_duration_sec,
  });
  master.add(tl, data.cta_start_sec);
}

// Pin master duration so renderer can read it. Expose for renderer.
master.duration(data.base_duration_sec);
(window as unknown as { __timelines: { overlay: gsap.core.Timeline } }).__timelines = {
  overlay: master,
};
