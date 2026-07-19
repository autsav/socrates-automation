import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedText } from "./AnimatedText";
import { Palette } from "../styles/theme";
import { WordTime } from "../lib/wordAt";

/**
 * HookScene — the opening pattern-interrupt. Word-by-word spring reveal with a
 * subtle whole-scene zoom-in on entrance and a fade+scale out at the end so it
 * hands off cleanly to the quote.
 */
export const HookScene: React.FC<{
  text: string;
  palette: Palette;
  wordTimes?: WordTime[];
}> = ({ text, palette, wordTimes }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const entrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
    durationInFrames: 20,
  });
  const enterScale = interpolate(entrance, [0, 1], [1.06, 1]);

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
  // 3-second hold window. Chunks cut hard (pattern interrupt), timed to the VO
  // word timings when present, equal splits otherwise.
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
        transform: `scale(${enterScale * outScale})`,
      }}
    >
      <AnimatedText
        text={chunk.text}
        palette={palette}
        fontSize={192}
        stagger={0.08}
        wordTimes={chunk.times}
        staticFirstFrames={chunk.index === 0 ? 3 : 0}
      />
    </div>
  );
};
