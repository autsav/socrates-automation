import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedText } from "./AnimatedText";
import { Palette } from "../styles/theme";
import { WordTime } from "../lib/wordAt";

const CHUNK = 7; // words per screen — bridge text is story prose, not a hook

/** BridgeScene — the story itself. Long-form narration (60s+ stories) is
 *  chunk-displayed CHUNK words at a time, each chunk cutting in when the VO
 *  reaches its first word (equal splits when no word timings exist) — the
 *  same big-type retention pattern HookScene uses, tuned for prose. Word
 *  timings stay scene-relative, so sliced chunks align with the VO as-is. */
export const BridgeScene: React.FC<{
  text: string;
  palette: Palette;
  wordTimes?: WordTime[];
  animSeed?: number;
}> = ({ text, palette, wordTimes, animSeed }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const entrance = spring({ frame, fps, config: { damping: 16, mass: 0.9, stiffness: 80 }, durationInFrames: 18 });
  const enterScale = interpolate(entrance, [0, 1], [1.04, 1]);
  const outFade = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const words = text.trim().split(/\s+/);
  const chunkCount = Math.max(1, Math.ceil(words.length / CHUNK));
  const wt = wordTimes ?? [];
  const chunkStart = (ci: number): number => {
    if (ci === 0) return 0;
    const wi = ci * CHUNK;
    if (wt.length > wi) return Math.round(wt[wi].start * fps);
    return Math.floor(((durationInFrames - 8) / chunkCount) * ci);
  };
  let active = 0;
  for (let ci = chunkCount - 1; ci >= 0; ci--) {
    if (frame >= chunkStart(ci)) { active = ci; break; }
  }
  const chunkText = words.slice(active * CHUNK, active * CHUNK + CHUNK).join(" ");
  const chunkTimes = wt.slice(active * CHUNK, active * CHUNK + CHUNK);
  const font = chunkCount > 1 ? 132 : 120;

  // Sentence-end tick: a 2-frame white flash right as a chunk cuts in, but
  // only when the previous chunk ended on a sentence boundary (cls "end") —
  // a punctuation beat for the cut, not every chunk change.
  const prevChunkLastWordCls =
    active > 0 ? wt[active * CHUNK - 1]?.cls : undefined;
  const showEndTick =
    active > 0 &&
    prevChunkLastWordCls === "end" &&
    frame - chunkStart(active) < 2;

  return (
    <div style={{ position: "absolute", inset: 0, opacity: outFade, transform: `scale(${enterScale})` }}>
      <AnimatedText
        text={chunkText}
        palette={palette}
        fontSize={font}
        stagger={0.06}
        wordTimes={chunkTimes}
        animSeed={animSeed}
      />
      {showEndTick ? (
        <AbsoluteFill
          style={{ background: "rgba(255,255,255,0.25)", pointerEvents: "none" }}
        />
      ) : null}
    </div>
  );
};
