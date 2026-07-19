import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedQuote } from "./AnimatedQuote";
import { FONT_FAMILY, Palette } from "../styles/theme";
import { WordTime } from "../lib/wordAt";

/**
 * QuoteScene — the payoff. The quote reveals word-by-word (slightly gentler
 * stagger than the hook), scaling 0.95 → 1.0, with the attribution springing up
 * from below once the quote has landed. An animated accent underline draws in
 * beneath the attribution.
 */
export const QuoteScene: React.FC<{
  quote: string;
  attribution: string;
  palette: Palette;
  beats?: number[];
  wordTimes?: WordTime[];
  staticFirstFrames?: number;
}> = ({ quote, attribution, palette, beats = [], wordTimes, staticFirstFrames = 0 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 16, mass: 0.9, stiffness: 80 },
    durationInFrames: 24,
  });
  const enterScale = interpolate(entrance, [0, 1], [0.95, 1]);

  const outFade = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Attribution springs in after the quote words have mostly revealed.
  const attribDelay = Math.round(fps * 1.1);
  const attribSpring = spring({
    frame: frame - attribDelay,
    fps,
    config: { damping: 13, mass: 0.7, stiffness: 110 },
    durationInFrames: 20,
  });
  const attribY = interpolate(attribSpring, [0, 1], [40, 0]);
  const attribOpacity = interpolate(attribSpring, [0, 0.7], [0, 1], {
    extrapolateRight: "clamp",
  });
  // Underline draws in beneath the attribution.
  const underline = interpolate(attribSpring, [0.3, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ position: "absolute", inset: 0, opacity: outFade }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          transform: `scale(${enterScale})`,
          // Lift the quote block up a touch to leave room for attribution.
          paddingBottom: "14%",
        }}
      >
        <AnimatedQuote
          staticFirstFrames={staticFirstFrames}
          quote={quote}
          palette={palette}
          beats={beats}
          fontSize={146}
          stagger={0.065}
          wordTimes={wordTimes}
        />
      </div>

      {/* Attribution + drawing underline, anchored below the quote block. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: "20%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 18,
          transform: `translateY(${attribY}px)`,
          opacity: attribOpacity,
        }}
      >
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 58,
            letterSpacing: "0.04em",
            color: palette.accent,
            textShadow: palette.dark
              ? `0 0 24px ${palette.glow}`
              : "0 2px 6px rgba(0,0,0,0.2)",
          }}
        >
          {attribution}
        </div>
        <div
          style={{
            height: 6,
            width: `${underline * 220}px`,
            borderRadius: 3,
            background: palette.accent,
            boxShadow: `0 0 16px ${palette.glow}`,
          }}
        />
      </div>
    </div>
  );
};
