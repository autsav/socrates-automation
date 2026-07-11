import React from "react";
import {
  interpolate,
  interpolateColors,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Palette } from "../styles/theme";

/**
 * GradientBg — an animated radial gradient that never sits still.
 *  - core color smoothly cycles through the mood's 3 bg stops (interpolateColors)
 *  - subtle zoom 1.0 → 1.1 over the scene
 *  - brightness pulse every ~1.5s
 *  - slow hue drift
 */
export const GradientBg: React.FC<{ palette: Palette }> = ({ palette }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;

  // Cycle the core color through the 3 gradient stops and back.
  const cyclePos = (Math.sin(t * Math.PI * 2 * 0.15) + 1) / 2; // 0..1
  const core = interpolateColors(
    cyclePos,
    [0, 0.5, 1],
    [palette.bg[0], palette.bg[1], palette.bg[0]]
  );
  const mid = palette.bg[1];
  const edge = palette.bg[0];

  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.12], {
    extrapolateRight: "clamp",
  });
  const brightness = 1 + 0.12 * Math.sin(t * Math.PI * 2 * 0.66);
  const hue = 10 * Math.sin(t * Math.PI * 2 * 0.2);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        transform: `scale(${zoom})`,
        filter: `brightness(${brightness}) hue-rotate(${hue}deg) saturate(1.15)`,
        background: `radial-gradient(circle at 50% 42%, ${core} 0%, ${mid} 38%, ${edge} 78%)`,
      }}
    />
  );
};
