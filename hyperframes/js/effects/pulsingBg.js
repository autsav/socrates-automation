/** Pulsing background: breathing vignette + subtle camera shake.
 *  Seek-safe: driven by a proxy object tweened by GSAP.
 */
export function buildPulsingBg(tl, durationSec) {
    const root = document.getElementById("root");
    if (!root)
        return;
    // Shake wrapper
    const wrapper = document.createElement("div");
    wrapper.style.position = "absolute";
    wrapper.style.inset = "-8px";
    wrapper.id = "shake-wrapper";
    // Move all existing children into wrapper
    while (root.firstChild) {
        wrapper.appendChild(root.firstChild);
    }
    root.appendChild(wrapper);
    // Vignette overlay
    const vignette = document.createElement("div");
    vignette.style.position = "absolute";
    vignette.style.inset = "0";
    vignette.style.pointerEvents = "none";
    vignette.id = "pulsing-vignette";
    wrapper.appendChild(vignette);
    // Grain overlay
    const grain = document.createElement("div");
    grain.style.position = "absolute";
    grain.style.inset = "0";
    grain.style.pointerEvents = "none";
    grain.style.opacity = "0.06";
    grain.style.mixBlendMode = "overlay";
    grain.style.backgroundImage =
        "url(\"data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";
    grain.style.backgroundSize = "240px 240px";
    wrapper.appendChild(grain);
    const state = { t: 0 };
    tl.to(state, {
        t: durationSec,
        duration: durationSec,
        ease: "none",
        onUpdate: () => {
            const t = state.t;
            const shakeX = 2.5 * Math.sin(t * Math.PI * 2 * 4) + 1.5 * Math.sin(t * Math.PI * 2 * 7);
            const shakeY = 2.5 * Math.cos(t * Math.PI * 2 * 5) + 1.5 * Math.sin(t * Math.PI * 2 * 9);
            wrapper.style.transform = `translate(${shakeX}px, ${shakeY}px)`;
            const isDark = getComputedStyle(root).getPropertyValue("--is-dark").trim() === "1";
            const vignetteStrength = 0.55 + 0.35 * ((Math.sin(t * Math.PI * 2 * 0.5) + 1) / 2);
            if (isDark) {
                vignette.style.background = `radial-gradient(circle at 50% 45%, rgba(0,0,0,0) 42%, rgba(0,0,0,${vignetteStrength}) 100%)`;
            }
            else {
                vignette.style.background = `radial-gradient(circle at 50% 45%, rgba(0,0,0,0) 48%, rgba(0,0,0,${vignetteStrength * 0.35}) 100%)`;
            }
        },
    }, 0);
}
