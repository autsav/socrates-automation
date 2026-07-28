/** Glitch text effect — RGB split on a target word.
 *  Creates red/cyan offset copies that jitter every few frames.
 *  Seek-safe: jitter offsets are computed from a deterministic time-based seed.
 */
import { mulberry32 } from "../lib/prng.js";
export function buildGlitchText(tl, startSec, durationSec, targetWordIndex, text, animSeed = 0) {
    const root = document.getElementById("root");
    if (!root)
        return;
    // Find the word span
    const wordEl = document.getElementById(`word-${targetWordIndex}`);
    if (!wordEl)
        return;
    // Create glitch overlay copies
    const container = document.createElement("div");
    container.style.position = "absolute";
    container.style.inset = "0";
    container.style.pointerEvents = "none";
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.justifyContent = "center";
    container.style.zIndex = "100";
    root.appendChild(container);
    const red = document.createElement("div");
    red.textContent = wordEl.textContent || "";
    red.style.position = "absolute";
    red.style.color = "#ff3b3b";
    red.style.opacity = "0";
    red.style.mixBlendMode = "screen";
    red.style.fontFamily = wordEl.style.fontFamily || getComputedStyle(wordEl).fontFamily;
    red.style.fontSize = wordEl.style.fontSize || getComputedStyle(wordEl).fontSize;
    red.style.fontWeight = "900";
    container.appendChild(red);
    const cyan = document.createElement("div");
    cyan.textContent = wordEl.textContent || "";
    cyan.style.position = "absolute";
    cyan.style.color = "#3bffff";
    cyan.style.opacity = "0";
    cyan.style.mixBlendMode = "screen";
    cyan.style.fontFamily = red.style.fontFamily;
    cyan.style.fontSize = red.style.fontSize;
    cyan.style.fontWeight = "900";
    container.appendChild(cyan);
    const rng = mulberry32(animSeed + targetWordIndex);
    // Jitter every ~3 frames (0.1s at 30fps)
    const state = { t: 0 };
    tl.to(state, {
        t: durationSec,
        duration: durationSec,
        ease: "none",
        onUpdate: () => {
            const bucket = Math.floor(state.t / 0.1);
            const rng2 = mulberry32(animSeed + targetWordIndex + bucket * 7919);
            const jx = (rng2() - 0.5) * 10;
            const jy = (rng2() - 0.5) * 6;
            const active = rng2() > 0.55;
            const glow = 20 + 14 * Math.sin(state.t * Math.PI * 2);
            if (active) {
                red.style.opacity = "0.7";
                cyan.style.opacity = "0.7";
                red.style.transform = `translate(${jx}px, ${jy}px)`;
                cyan.style.transform = `translate(${-jx}px, ${-jy}px)`;
                wordEl.style.textShadow = `0 0 ${glow}px var(--glow, #ffd78c)`;
            }
            else {
                red.style.opacity = "0";
                cyan.style.opacity = "0";
                wordEl.style.textShadow = "";
            }
        },
    }, startSec);
}
