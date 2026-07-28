import { mulberry32 } from "../lib/prng.js";
const COUNT = 26;
export function buildParticleField(tl, durationSec, animSeed = 0) {
    const root = document.getElementById("root");
    if (!root)
        return;
    const rng = mulberry32(animSeed || 42);
    const width = 1080;
    const height = 1920;
    const particles = [];
    // Create particle elements
    for (let i = 0; i < COUNT; i++) {
        const el = document.createElement("div");
        el.style.position = "absolute";
        el.style.borderRadius = "50%";
        el.style.pointerEvents = "none";
        root.appendChild(el);
        const colorIdx = i % 3;
        const colorVar = `var(--particle-${colorIdx + 1}, #fff)`;
        const size = 4 + rng() * 16;
        const baseX = rng() * width;
        const speed = 30 + rng() * 90;
        const wobbleAmp = 12 + rng() * 40;
        const wobbleFreq = 0.3 + rng() * 0.9;
        const startY = height + rng() * height;
        const baseOpacity = 0.25 + rng() * 0.5;
        el.style.width = `${size}px`;
        el.style.height = `${size}px`;
        el.style.background = colorVar;
        el.style.filter = `blur(${size > 12 ? 2 : 0.5}px)`;
        el.style.boxShadow = `0 0 ${size * 1.5}px ${colorVar}`;
        particles.push({ el, baseX, size, speed, wobbleAmp, wobbleFreq, startY, baseOpacity, color: colorVar });
    }
    // Animate each particle
    for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const totalTravel = height + 200;
        // Use gsap.set for initial position, then animate
        // We'll create a custom animation that wraps vertically
        const obj = { t: 0 };
        tl.to(obj, {
            t: durationSec,
            duration: durationSec,
            ease: "none",
            onUpdate: () => {
                const t = obj.t;
                const y = ((p.startY - p.speed * t) % totalTravel + totalTravel) % totalTravel - 100;
                const x = p.baseX + Math.sin(t * Math.PI * 2 * p.wobbleFreq + i) * p.wobbleAmp;
                const lifeFade = Math.min(1, t / 0.33) * Math.min(1, (durationSec - t) / 0.4);
                p.el.style.left = `${x}px`;
                p.el.style.top = `${y}px`;
                p.el.style.opacity = `${p.baseOpacity * lifeFade}`;
            },
        }, 0);
    }
}
