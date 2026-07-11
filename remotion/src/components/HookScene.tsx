import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedText } from "./AnimatedText";
import { Palette } from "../styles/theme";

/**
 * HookScene — the opening pattern-interrupt. Word-by-word spring reveal with a
 * subtle whole-scene zoom-in on entrance and a fade+scale out at the end so it
 * hands off cleanly to the quote.
 */
export const HookScene: React.FC<{ text: string; palette: Palette }> = ({
  text,
  palette,
}) => {
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
        text={text}
        palette={palette}
        fontSize={168}
        stagger={0.08}
      />
    </div>
  );
};
