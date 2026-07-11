import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Palette } from "../styles/theme";

/**
 * PulsingBg — the tension layer over the gradient + particles:
 *  - a vignette that breathes (edges darken and release)
 *  - a subtle 2-3px shake for urgency
 *  - a faint grain overlay
 * Returns a wrapper that shakes its children plus the vignette/grain overlays.
 */
export const PulsingBg: React.FC<{
  palette: Palette;
  children: React.ReactNode;
}> = ({ palette, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  // 2-3px shake — two summed sines so it never looks periodic.
  const shakeX = 2.5 * Math.sin(t * Math.PI * 2 * 4) + 1.5 * Math.sin(t * Math.PI * 2 * 7);
  const shakeY = 2.5 * Math.cos(t * Math.PI * 2 * 5) + 1.5 * Math.sin(t * Math.PI * 2 * 9);

  // Vignette breathing: opacity oscillates.
  const vignetteStrength = interpolate(
    Math.sin(t * Math.PI * 2 * 0.5),
    [-1, 1],
    [0.55, 0.9]
  );

  return (
    <div
      style={{
        position: "absolute",
        inset: -8,
        transform: `translate(${shakeX}px, ${shakeY}px)`,
      }}
    >
      {children}
      {/* Breathing vignette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: palette.dark
            ? `radial-gradient(circle at 50% 45%, rgba(0,0,0,0) 42%, rgba(0,0,0,${vignetteStrength}) 100%)`
            : `radial-gradient(circle at 50% 45%, rgba(0,0,0,0) 48%, rgba(0,0,0,${
                vignetteStrength * 0.35
              }) 100%)`,
        }}
      />
      {/* Grain overlay — repeating tiny noise via SVG data URI */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          opacity: 0.06,
          mixBlendMode: "overlay",
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")",
          backgroundSize: "240px 240px",
        }}
      />
    </div>
  );
};
