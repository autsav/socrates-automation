import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedText } from "./AnimatedText";
import { Palette } from "../styles/theme";
import { WordTime } from "../lib/wordAt";

/** BridgeScene — the pivot from the trending hook into the timeless quote. */
export const BridgeScene: React.FC<{
  text: string;
  palette: Palette;
  wordTimes?: WordTime[];
}> = ({ text, palette, wordTimes }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const entrance = spring({ frame, fps, config: { damping: 16, mass: 0.9, stiffness: 80 }, durationInFrames: 18 });
  const enterScale = interpolate(entrance, [0, 1], [1.04, 1]);
  const outFade = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", inset: 0, opacity: outFade, transform: `scale(${enterScale})` }}>
      <AnimatedText text={text} palette={palette} fontSize={120} stagger={0.06} wordTimes={wordTimes} />
    </div>
  );
};
