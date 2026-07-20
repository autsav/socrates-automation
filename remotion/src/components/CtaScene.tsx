import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FONT_FAMILY, Palette } from "../styles/theme";

/**
 * CtaScene — the close. The CTA slides up from the bottom with a springy bounce
 * and then pulses (scale + glow) to draw the eye toward the save/follow action.
 */
export const CtaScene: React.FC<{
  text: string;
  palette: Palette;
  /** Frame (scene-relative) the CTA VO ends — drives a freeze-pop punch once
   *  the words have settled, so the save/follow beat lands with the audio. */
  voEndFrame?: number;
}> = ({ text, palette, voEndFrame }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;

  // Slide up from bottom with an overshooting spring (bounce on arrival).
  const arrival = spring({
    frame,
    fps,
    config: { damping: 9, mass: 0.8, stiffness: 130 },
    durationInFrames: 26,
  });
  const slideY = interpolate(arrival, [0, 1], [220, 0]);
  const opacity = interpolate(arrival, [0, 0.5], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Attention pulse once it has arrived.
  const pulse = 1 + 0.04 * Math.sin(t * Math.PI * 2 * 1.4);
  const glow = 24 + 20 * (0.5 + 0.5 * Math.sin(t * Math.PI * 2 * 1.4));

  // Freeze-pop (spec 3): once the VO ends and the words have settled, a
  // brief extra punch over 8 frames — a beat for the save/follow action.
  const freezePop =
    voEndFrame !== undefined && frame >= voEndFrame && frame <= voEndFrame + 8
      ? 1 + 0.06 * (1 - Math.abs(frame - voEndFrame - 4) / 4)
      : 1;

  const outFade = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const fontSize = text.length > 34 ? 118 : 138;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: outFade,
      }}
    >
      <div
        style={{
          transform: `translateY(${slideY}px) scale(${pulse * freezePop})`,
          opacity,
          padding: "0 6%",
          textAlign: "center",
          fontFamily: FONT_FAMILY,
          fontWeight: 900,
          fontSize,
          lineHeight: 1.05,
          letterSpacing: "-0.01em",
          color: palette.text,
          WebkitTextStroke: `${Math.max(2, fontSize * 0.02)}px ${palette.stroke}`,
          paintOrder: "stroke fill",
          textShadow: palette.dark
            ? `0 0 ${glow}px ${palette.glow}, 0 6px 10px rgba(0,0,0,0.8)`
            : "0 4px 10px rgba(0,0,0,0.22)",
        }}
      >
        {text}
      </div>
    </div>
  );
};
