import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONT_FAMILY, Palette } from "../styles/theme";
import { autoFontSize } from "./AnimatedText";
import { pickEmphasisIndex } from "../lib/emphasis";

export interface AnimatedQuoteProps {
  quote: string;
  palette: Palette;
  /** Scene-relative seconds of detected beats (0 = quote-scene start). */
  beats?: number[];
  /** Scene-relative frame at which the reveal starts. */
  startFrame?: number;
  fontSize?: number;
  /** Stagger between words, seconds. */
  stagger?: number;
}

/** Smallest scene-relative beat frame at or after `notBefore`, else null.
 *  `beats` are already scene-relative, so the frame is round(t*fps). */
function nearestBeatFrame(
  beats: number[],
  fps: number,
  notBefore: number
): number | null {
  let best: number | null = null;
  for (const t of beats) {
    const rel = Math.round(t * fps);
    if (rel >= notBefore) best = best === null ? rel : Math.min(best, rel);
  }
  return best;
}

export const AnimatedQuote: React.FC<AnimatedQuoteProps> = ({
  quote,
  palette,
  beats = [],
  startFrame = 0,
  fontSize = 146,
  stagger = 0.065,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = quote.trim().split(/\s+/);
  const size = autoFontSize(quote, fontSize);
  const staggerFrames = stagger * fps;
  const emphasis = pickEmphasisIndex(words);

  // Frame at which the emphasis word has finished revealing.
  const emphasisRevealEnd = startFrame + emphasis * staggerFrames + 24;
  // Punch fires on the nearest beat after that, else ~8 frames after reveal.
  const beatFrame = nearestBeatFrame(beats, fps, emphasisRevealEnd);
  const triggerFrame = beatFrame ?? emphasisRevealEnd + 8;
  const punch = interpolate(
    frame,
    [triggerFrame - 3, triggerFrame, triggerFrame + 6],
    [1, 1.14, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Quote-mark bloom: springs in ~6 frames before the first word.
  const bloomSpring = spring({
    frame: frame - (startFrame - 6),
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
    durationInFrames: 22,
  });
  const bloomScale = interpolate(bloomSpring, [0, 1], [0.6, 1]);
  const bloomOpacity = interpolate(bloomSpring, [0, 1], [0, 0.22]);

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {/* #20 Quote-mark bloom — decorative, behind the words. */}
      <div
        style={{
          position: "absolute",
          top: "16%",
          left: "8%",
          fontFamily: FONT_FAMILY,
          fontWeight: 900,
          fontSize: size * 2.6,
          lineHeight: 1,
          color: palette.accent,
          opacity: bloomOpacity,
          transform: `scale(${bloomScale})`,
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        &ldquo;
      </div>

      {/* #2 Masked rise + #5 keyword punch. */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexWrap: "wrap",
          alignContent: "center",
          justifyContent: "center",
          alignItems: "center",
          gap: `${size * 0.04}px ${size * 0.16}px`,
          padding: "0 6%",
          textAlign: "center",
        }}
      >
        {words.map((word, i) => {
          const wordStart = startFrame + i * staggerFrames;
          const enter = spring({
            frame: frame - wordStart,
            fps,
            config: { damping: 14, mass: 0.7, stiffness: 90 },
            durationInFrames: 24,
          });
          // Mask rise: word translates up from one line-height below.
          const rise = interpolate(enter, [0, 1], [size * 1.1, 0]);
          const opacity = interpolate(enter, [0, 0.5], [0, 1], {
            extrapolateRight: "clamp",
          });
          const isEmphasis = i === emphasis;
          const scale = isEmphasis ? punch : 1;
          const color = isEmphasis ? palette.accent : palette.text;

          return (
            <span
              key={`${word}-${i}`}
              style={{
                display: "inline-block",
                overflow: "hidden",
                paddingBottom: size * 0.12,
                marginBottom: -size * 0.12,
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  fontFamily: FONT_FAMILY,
                  fontWeight: 900,
                  fontSize: size,
                  lineHeight: 1.02,
                  letterSpacing: "-0.01em",
                  color,
                  opacity,
                  transform: `translateY(${rise}px) scale(${scale})`,
                  WebkitTextStroke: `${Math.max(2, size * 0.02)}px ${palette.stroke}`,
                  paintOrder: "stroke fill",
                  textShadow: palette.dark
                    ? `0 0 28px ${palette.glow}, 0 ${size * 0.03}px ${size * 0.05}px rgba(0,0,0,0.85)`
                    : `0 ${size * 0.02}px ${size * 0.04}px rgba(0,0,0,0.25)`,
                }}
              >
                {word}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
};
