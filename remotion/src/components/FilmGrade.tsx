import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

/** Cinematic pass: letterbox bars + animated grain. Sits above the background,
 *  below text. Pure visuals — no runtime failure path. */
export const FilmGrade: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const barPct = 8;
  // Grain: jitter an SVG-noise tile's offset per frame.
  const gx = (frame * 37) % 100;
  const gy = (frame * 53) % 100;
  return (
    <AbsoluteFill>
      {children}
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          opacity: 0.07,
          backgroundImage:
            `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
          backgroundPosition: `${gx}px ${gy}px`,
        }}
      />
      <div style={{ position: "absolute", top: 0, left: 0, right: 0,
                    height: `${barPct}%`, background: "black" }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0,
                    height: `${barPct}%`, background: "black" }} />
    </AbsoluteFill>
  );
};
