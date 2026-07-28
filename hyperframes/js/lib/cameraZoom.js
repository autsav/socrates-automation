function lerp(a, b, t) {
    return a + (b - a) * t;
}
function clamp(n, min, max) {
    return Math.min(Math.max(n, min), max);
}
/** Slow camera push (1.0 → 1.06 over the reel) plus a short decaying scale kick
 *  on each beat frame. `beatFrames` are absolute composition frames. */
export function cameraScale(frame, durationInFrames, beatFrames) {
    const t = clamp(frame / durationInFrames, 0, 1);
    const base = lerp(1.0, 1.06, t);
    const KICK = 0.05;
    const WIN = 6;
    let kick = 0;
    for (const bf of beatFrames) {
        if (frame >= bf && frame <= bf + WIN) {
            kick = Math.max(kick, KICK * (1 - (frame - bf) / WIN));
        }
    }
    return base + kick;
}
