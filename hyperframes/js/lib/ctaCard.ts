// CTA card fade-in / fade-out animations (relative timeline).
//
// Helper timeline is RELATIVE — all tweens position from t=0. The orchestrator
// (Task 5) drops the child into the master via `master.add(childTl, atSec)`.

import gsap from "gsap";

export interface CtaSpec {
  copy: string;
  url?: string;
  durationSec: number;
}

export function ctaCard(spec: CtaSpec): gsap.core.Timeline {
  const tl = gsap.timeline();
  // 0 → 0.3: from(opacity 0, y 50) entrance
  tl.from(
    "#cta-card",
    { opacity: 0, y: 50, duration: 0.3, ease: "power2.out" },
    0,
  );
  // Visible label at 0.3s (relative)
  tl.addLabel("cta_visible", 0.3);
  // 0.1 → 0.3: settle to opacity 1, y 0
  tl.to(
    "#cta-card",
    { opacity: 1, y: 0, duration: 0.2, ease: "power2.out" },
    0.1,
  );
  // durationSec → durationSec + 0.2: exit
  tl.to(
    "#cta-card",
    { opacity: 0, y: -50, duration: 0.2 },
    spec.durationSec,
  );
  return tl;
}
