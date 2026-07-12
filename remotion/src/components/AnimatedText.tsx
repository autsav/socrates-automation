import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONT_FAMILY, Palette } from "../styles/theme";
import { wordAt, WordTime } from "../lib/wordAt";

/**
 * AnimatedText — HUGE, bold, centered text that reveals word-by-word with
 * spring physics. Each word scales up from 0.8 → 1.0 and rises a few px,
 * staggered 80ms apart, with a pulsing glow. This is the whole point of the
 * Remotion editor: broadcast-quality, physics-driven text motion.
 */

export interface AnimatedTextProps {
  text: string;
  palette: Palette;
  /** Frame (relative to this sequence) at which the reveal starts. */
  startFrame?: number;
  /** Base font size in px. Auto-shrinks for longer text. */
  fontSize?: number;
  /** Stagger between words, in seconds (default 0.08 = 80ms). */
  stagger?: number;
  /** Font weight. */
  weight?: number;
  /** Extra style overrides for the container. */
  maxWidthPct?: number;
  /** Per-word VO timings (scene-relative seconds); drives karaoke reveal when present. */
  wordTimes?: WordTime[];
}

/** Estimate a font size so the longest word and total text fill ~80%+ width
 *  without overflowing. Simple heuristic tuned for the 1080px canvas. */
export function autoFontSize(text: string, base: number): number {
  const words = text.trim().split(/\s+/);
  const charCount = text.replace(/\s+/g, "").length;
  const longest = words.reduce((m, w) => Math.max(m, w.length), 0);
  let size = base;
  // Shrink for total length (more words → smaller so it fits vertically).
  if (charCount > 28) size = base * 0.82;
  if (charCount > 48) size = base * 0.66;
  if (charCount > 72) size = base * 0.54;
  if (charCount > 100) size = base * 0.46;
  // Never let the single longest word overflow ~92% of width.
  const maxForLongest = (1080 * 0.92) / (longest * 0.62);
  return Math.floor(Math.min(size, maxForLongest));
}

export const AnimatedText: React.FC<AnimatedTextProps> = ({
  text,
  palette,
  startFrame = 0,
  fontSize = 150,
  stagger = 0.08,
  weight = 900,
  maxWidthPct = 90,
  wordTimes = [],
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.trim().split(/\s+/);
  const size = autoFontSize(text, fontSize);
  const staggerFrames = stagger * fps;

  // Glow that breathes for the whole element.
  const glowPulse = interpolate(
    Math.sin((frame / fps) * Math.PI * 2 * 0.9),
    [-1, 1],
    [0.35, 1]
  );
  const glowRadius = 18 + glowPulse * 34;

  return (
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
        padding: `0 ${(100 - maxWidthPct) / 2}%`,
        textAlign: "center",
      }}
    >
      {words.map((word, i) => {
        const wordStart =
          wordTimes.length > i
            ? Math.round(wordTimes[i].start * fps)
            : startFrame + i * staggerFrames;
        const enter = spring({
          frame: frame - wordStart,
          fps,
          config: { damping: 12, mass: 0.6, stiffness: 120 },
          durationInFrames: 24,
        });
        const scale = interpolate(enter, [0, 1], [0.8, 1]);
        const translateY = interpolate(enter, [0, 1], [28, 0]);
        const opacity = interpolate(enter, [0, 0.6], [0, 1], {
          extrapolateRight: "clamp",
        });

        return (
          <span
            key={`${word}-${i}`}
            style={{
              display: "inline-block",
              fontFamily: FONT_FAMILY,
              fontWeight: weight,
              fontSize: size,
              lineHeight: 1.02,
              letterSpacing: "-0.01em",
              color: palette.text,
              opacity,
              transform: `translateY(${translateY}px) scale(${scale})`,
              // Heavy contrast outline + pulsing glow so the text is razor-legible
              // over the moving, pulsing background.
              WebkitTextStroke: `${Math.max(2, size * 0.02)}px ${palette.stroke}`,
              paintOrder: "stroke fill",
              textShadow: palette.dark
                ? `0 0 ${glowRadius}px ${palette.glow}, 0 ${size * 0.03}px ${
                    size * 0.05
                  }px rgba(0,0,0,0.85)`
                : `0 ${size * 0.02}px ${size * 0.04}px rgba(0,0,0,0.25)`,
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};
