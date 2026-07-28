/** Cinematic film grade: letterbox bars + animated grain overlay.
 *  Creates overlay elements and animates grain position via GSAP.
 */
export function buildFilmGrade(tl, durationSec) {
    const root = document.getElementById("root");
    if (!root)
        return;
    // Grain overlay
    const grain = document.createElement("div");
    grain.style.position = "absolute";
    grain.style.inset = "0";
    grain.style.pointerEvents = "none";
    grain.style.opacity = "0.07";
    grain.style.backgroundImage = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`;
    root.appendChild(grain);
    // Letterbox bars
    const topBar = document.createElement("div");
    topBar.style.position = "absolute";
    topBar.style.top = "0";
    topBar.style.left = "0";
    topBar.style.right = "0";
    topBar.style.height = "8%";
    topBar.style.background = "black";
    topBar.style.pointerEvents = "none";
    root.appendChild(topBar);
    const botBar = document.createElement("div");
    botBar.style.position = "absolute";
    botBar.style.bottom = "0";
    botBar.style.left = "0";
    botBar.style.right = "0";
    botBar.style.height = "8%";
    botBar.style.background = "black";
    botBar.style.pointerEvents = "none";
    root.appendChild(botBar);
    // Animate grain position
    const state = { frame: 0 };
    tl.to(state, {
        frame: durationSec * 30, // fps
        duration: durationSec,
        ease: "none",
        onUpdate: () => {
            const f = Math.floor(state.frame);
            const gx = (f * 37) % 100;
            const gy = (f * 53) % 100;
            grain.style.backgroundPosition = `${gx}px ${gy}px`;
        },
    }, 0);
}
