import { interpolate } from "remotion";

/** Slow camera push (1.0 → 1.06 over the reel) plus a short decaying scale kick
 *  on each beat frame. `beatFrames` are absolute composition frames. */
export function cameraScale(
  frame: number,
  durationInFrames: number,
  beatFrames: number[]
): number {
  const base = interpolate(frame, [0, durationInFrames], [1.0, 1.06], {
    extrapolateRight: "clamp",
  });
  const KICK = 0.02;
  const WIN = 6;
  let kick = 0;
  for (const bf of beatFrames) {
    if (frame >= bf && frame <= bf + WIN) {
      kick = Math.max(kick, KICK * (1 - (frame - bf) / WIN));
    }
  }
  return base + kick;
}
