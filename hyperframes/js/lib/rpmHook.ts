// RPM hook intro animations (pop / slide / fade).
//
// Helper timeline is RELATIVE — all tweens position from t=0. The orchestrator
// (Task 5) drops the child into the master via `master.add(childTl, atSec)`.
// Dropping `atSec` from the spec avoids double-offsetting the timeline.

import gsap from "gsap";

export type RpmHookStyle = "pop" | "slide" | "fade";

export interface RpmHookSpec {
  text: string;
  durationSec: number;
  style: RpmHookStyle;
}

export function rpmHook(spec: RpmHookSpec): gsap.core.Timeline {
  const tl = gsap.timeline();
  // Entrance label always at t=0 (relative). Orchestrator composes at scene time.
  tl.addLabel("rpm_entrance", 0);

  if (spec.style === "pop") {
    // 0 → 0.3: from(scale 0, rotate -180) → 0.3 → 0.5: to(scale 1, rotate 0)
    tl.from(
      "#rpm-hook",
      { scale: 0, rotation: -180, duration: 0.3, ease: "back.out" },
      0,
    );
    tl.to(
      "#rpm-hook",
      { scale: 1, rotation: 0, duration: 0.2, ease: "power2.out" },
      0.3,
    );
  } else if (spec.style === "slide") {
    // 0 → 0.4: from(x -200, opacity 0)
    tl.from(
      "#rpm-hook",
      { x: -200, opacity: 0, duration: 0.4, ease: "power2.out" },
      0,
    );
  } else {
    // fade: 0 → 0.5: from(opacity 0)
    tl.from("#rpm-hook", { opacity: 0, duration: 0.5 }, 0);
  }

  // Exit at durationSec → durationSec + 0.2
  const exitStart = spec.durationSec;
  tl.to("#rpm-hook", { opacity: 0, duration: 0.2 }, exitStart);

  return tl;
}
