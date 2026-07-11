import React from "react";
import { useCurrentFrame, useVideoConfig, random } from "remotion";
import { FONT_FAMILY, Palette } from "../styles/theme";

/**
 * GlitchText — an RGB-split glitch treatment for short, punchy words (e.g. an
 * emphasis word in a hook). Chromatic aberration offsets jitter deterministically
 * a few frames at a time. Optional accent — kept available for scenes that want
 * an aggressive pattern-interrupt look.
 */
export const GlitchText: React.FC<{
  text: string;
  palette: Palette;
  fontSize?: number;
}> = ({ text, palette, fontSize = 150 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Jitter every few frames so the glitch reads as digital, not smooth.
  const bucket = Math.floor(frame / 3);
  const jx = (random(`gx-${bucket}`) - 0.5) * 10;
  const jy = (random(`gy-${bucket}`) - 0.5) * 6;
  const active = random(`ga-${bucket}`) > 0.55;
  const t = frame / fps;
  const glow = 20 + 14 * Math.sin(t * Math.PI * 2);

  const base: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: FONT_FAMILY,
    fontWeight: 900,
    fontSize,
    color: palette.text,
    WebkitTextStroke: `${Math.max(2, fontSize * 0.02)}px ${palette.stroke}`,
    paintOrder: "stroke fill",
  };

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {active && (
        <div style={{ ...base, color: "#ff3b3b", transform: `translate(${jx}px,${jy}px)`, opacity: 0.7, mixBlendMode: "screen" }}>
          {text}
        </div>
      )}
      {active && (
        <div style={{ ...base, color: "#3bffff", transform: `translate(${-jx}px,${-jy}px)`, opacity: 0.7, mixBlendMode: "screen" }}>
          {text}
        </div>
      )}
      <div style={{ ...base, textShadow: `0 0 ${glow}px ${palette.glow}` }}>{text}</div>
    </div>
  );
};
