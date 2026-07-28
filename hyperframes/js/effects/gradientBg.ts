/** Breathing radial gradient background.
 *  Cycles core color through mood bg stops, zooms, pulses brightness/hue.
 *  Seek-safe: all values driven by a proxy object tweened by GSAP.
 */
export function buildGradientBg(
  tl: gsap.core.Timeline,
  durationSec: number,
): void {
  const el = document.querySelector(".gradient-bg") as HTMLElement | null;
  if (!el) return;

  // Read CSS vars for the 3 bg stops
  const style = getComputedStyle(el);
  const outer = style.getPropertyValue("--bg-outer").trim() || "#000";
  const core = style.getPropertyValue("--bg-core").trim() || "#333";

  // Proxy object that GSAP tweens; onUpdate writes the gradient string.
  const state = { cycle: 0, zoom: 1, brightness: 1, hue: 0 };

  tl.to(state, {
    cycle: 1,
    duration: durationSec,
    ease: "none",
    onUpdate: () => {
      const c = state.cycle;
      // Cycle core color: 0->outer, 0.5->core, 1->outer
      const coreColor = c < 0.5
        ? interpolateColor(outer, core, c * 2)
        : interpolateColor(core, outer, (c - 0.5) * 2);
      const b = 1 + 0.12 * Math.sin(state.cycle * Math.PI * 2 * 0.66 * durationSec);
      const h = 10 * Math.sin(state.cycle * Math.PI * 2 * 0.2 * durationSec);
      el.style.transform = `scale(${1 + 0.12 * state.cycle})`;
      el.style.filter = `brightness(${b}) hue-rotate(${h}deg) saturate(1.15)`;
      el.style.background = `radial-gradient(circle at 50% 42%, ${coreColor} 0%, ${core} 38%, ${outer} 78%)`;
    },
  }, 0);
}

/** Linearly interpolate between two hex colors. */
function interpolateColor(a: string, b: string, t: number): string {
  const ah = parseInt(a.replace("#", ""), 16);
  const bh = parseInt(b.replace("#", ""), 16);
  const ar = (ah >> 16) & 0xff, ag = (ah >> 8) & 0xff, ab = ah & 0xff;
  const br = (bh >> 16) & 0xff, bg = (bh >> 8) & 0xff, bb = bh & 0xff;
  const rr = Math.round(ar + (br - ar) * t);
  const rg = Math.round(ag + (bg - ag) * t);
  const rb = Math.round(ab + (bb - ab) * t);
  return `#${((rr << 16) | (rg << 8) | rb).toString(16).padStart(6, "0")}`;
}
