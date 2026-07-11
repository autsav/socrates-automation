export interface DuckSpan {
  start: number; // frame
  end: number; // frame
}

/**
 * Music-bed gain at `frame`: `base` outside VO spans, `duck` inside, with a
 * linear `ramp`-frame edge on each side of every span. Overlapping effects take
 * the lowest gain.
 */
export function duckVolume(
  frame: number,
  spans: DuckSpan[],
  opts?: { base?: number; duck?: number; ramp?: number }
): number {
  const base = opts?.base ?? 0.32;
  const duck = opts?.duck ?? 0.12;
  const ramp = opts?.ramp ?? 6;
  let v = base;
  for (const s of spans) {
    if (frame >= s.start && frame <= s.end) return duck;
    if (frame >= s.start - ramp && frame < s.start) {
      const t = (frame - (s.start - ramp)) / ramp; // 0..1
      v = Math.min(v, base + (duck - base) * t);
    }
    if (frame > s.end && frame <= s.end + ramp) {
      const t = (frame - s.end) / ramp; // 0..1
      v = Math.min(v, duck + (base - duck) * t);
    }
  }
  return v;
}
