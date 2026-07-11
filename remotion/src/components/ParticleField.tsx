import React from "react";
import { random, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { Palette } from "../styles/theme";

/**
 * ParticleField — 26 mood-colored particles that drift upward across the field.
 * Each has its own size, speed, opacity and horizontal wobble. Deterministic
 * via Remotion's seeded random() so every frame renders identically.
 */
const COUNT = 26;

export const ParticleField: React.FC<{ palette: Palette }> = ({ palette }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const t = frame / fps;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {new Array(COUNT).fill(0).map((_, i) => {
        const seed = `p-${i}`;
        const baseX = random(`${seed}-x`) * width;
        const size = 4 + random(`${seed}-s`) * 16;
        const speed = 30 + random(`${seed}-v`) * 90; // px/sec upward
        const wobbleAmp = 12 + random(`${seed}-w`) * 40;
        const wobbleFreq = 0.3 + random(`${seed}-f`) * 0.9;
        const startY = height + random(`${seed}-y`) * height;
        const baseOpacity = 0.25 + random(`${seed}-o`) * 0.5;
        const color = palette.particles[i % palette.particles.length];

        // Wrap vertically so the field stays populated across the whole scene.
        const totalTravel = height + 200;
        const y =
          ((startY - speed * t) % totalTravel + totalTravel) % totalTravel - 100;
        const x = baseX + Math.sin(t * Math.PI * 2 * wobbleFreq + i) * wobbleAmp;

        // Fade in at start, fade out near the end of the scene.
        const lifeFade = interpolate(
          frame,
          [0, 10, durationInFrames - 12, durationInFrames],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: size,
              height: size,
              borderRadius: "50%",
              background: color,
              opacity: baseOpacity * lifeFade,
              filter: `blur(${size > 12 ? 2 : 0.5}px)`,
              boxShadow: `0 0 ${size * 1.5}px ${color}`,
            }}
          />
        );
      })}
    </div>
  );
};
