/** Color grade: CSS filter on content + vignette + subtle grain.
 *  Reads the mood's grade from getGrade and applies as overlays.
 */
import { getGrade } from "../lib/getGrade.js";

const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

export function buildColorGrade(
  tl: gsap.core.Timeline,
  durationSec: number,
  mood: string,
): void {
  const root = document.getElementById("root");
  if (!root) return;

  const grade = getGrade(mood);

  // Filter layer — applies the mood's CSS filter to everything beneath it
  const filterLayer = document.createElement("div");
  filterLayer.style.position = "absolute";
  filterLayer.style.inset = "0";
  filterLayer.style.filter = grade.filter;
  filterLayer.style.pointerEvents = "none";
  root.appendChild(filterLayer);

  // Vignette overlay
  const vignette = document.createElement("div");
  vignette.style.position = "absolute";
  vignette.style.inset = "0";
  vignette.style.pointerEvents = "none";
  vignette.style.background = `radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,${grade.vignette}) 100%)`;
  root.appendChild(vignette);

  // Grain overlay
  const grain = document.createElement("div");
  grain.style.position = "absolute";
  grain.style.inset = "0";
  grain.style.pointerEvents = "none";
  grain.style.backgroundImage = GRAIN;
  grain.style.opacity = "0.06";
  grain.style.mixBlendMode = "overlay";
  root.appendChild(grain);

  // Breathing vignette opacity
  const state = { breathe: 0 };
  tl.to(state, {
    breathe: 1,
    duration: durationSec,
    ease: "none",
    onUpdate: () => {
      const b = 0.55 + 0.35 * Math.sin(state.breathe * Math.PI * 2 * 0.5);
      vignette.style.background = `radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,${Math.min(1, b * grade.vignette)}) 100%)`;
    },
  }, 0);
}
