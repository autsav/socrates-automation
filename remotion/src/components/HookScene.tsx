import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedText } from "./AnimatedText";
import { Palette } from "../styles/theme";
import { WordTime } from "../lib/wordAt";

/**
 * HookScene — the opening pattern-interrupt. The first 1-3 seconds decide
 * retention, so the entrance is a HARD pop (not a soft spring): 1.18 -> 1.0 in
 * 6 frames + a 2-frame jolt. A scroller's eye is gone by frame 6 if nothing
 * moved hard. Word-by-word reveal with a fade+scale out so it hands off cleanly
 * to the quote.
 */
export const HookScene: React.FC<{
  text: string;
  palette: Palette;
  wordTimes?: WordTime[];
  animSeed?: number;
}> = ({ text, palette, wordTimes, animSeed }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Frame-0 HARD pop: 1.18 -> 1.0 in 6 frames (replaces the soft 20-frame spring).
  // This is the scroll-stopper — the algorithm rewards an immediate visual move.
  const hardPop = interpolate(frame, [0, 6], [1.18, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // 2-frame entry jolt: a hard x-shift the eye can't ignore (pattern interrupt).
  const jolt = frame < 2 ? (frame % 2 === 0 ? -6 : 6) : 0;

  const outFade = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const outScale = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 1.05],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Big-type retention pattern (recipe #2): show <=4 words at a time during the
  // hold window. Chunks cut hard (pattern interrupt), timed to the VO word
  // timings when present, equal splits otherwise.
  const words = text.trim().split(/\s+/);
  const chunkCount = Math.max(1, Math.ceil(words.length / 4));
  const wt = wordTimes ?? [];
  const chunkStart = (ci: number): number => {
    if (ci === 0) return 0;
    const wi = ci * 4;
    if (wt.length > wi) return Math.round(wt[wi].start * fps);
    return Math.floor(((durationInFrames - 8) / chunkCount) * ci);
  };
  let active = 0;
  for (let ci = chunkCount - 1; ci >= 0; ci--) {
    if (frame >= chunkStart(ci)) { active = ci; break; }
  }
  const chunk = {
    index: active,
    text: words.slice(active * 4, active * 4 + 4).join(" "),
    times: wt.slice(active * 4, active * 4 + 4),
  };

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity: outFade,
        transform: `translateX(${jolt}px) scale(${hardPop * outScale})`,
      }}
    >
      <AnimatedText
        text={chunk.text}
        palette={palette}
        fontSize={192}
        stagger={0.06}
        wordTimes={chunk.times}
        staticFirstFrames={chunk.index === 0 ? 3 : 0}
        animSeed={animSeed}
        hookMode
      />
    </div>
  );
};
