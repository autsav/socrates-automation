import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { BackgroundPhoto } from "./BackgroundPhoto";

/** Multi-clip background: each clip owns a span of the reel, cutting on the
 *  given frame boundaries (scene starts + mid-bridge stress points). One clip
 *  → identical to BackgroundPhoto. */
export const BackgroundReel: React.FC<{
  clips: string[];
  clipDurationsSec: number[];
  cutFrames: number[]; // ascending, first must be 0
}> = ({ clips, clipDurationsSec, cutFrames }) => {
  const { durationInFrames } = useVideoConfig();
  if (clips.length === 0) return null;
  if (clips.length === 1) {
    return <BackgroundPhoto src={clips[0]} videoDurationSec={clipDurationsSec[0]} />;
  }
  const starts = cutFrames.length ? cutFrames : [0];
  return (
    <AbsoluteFill>
      {clips.map((clip, i) => {
        const from = starts[Math.min(i, starts.length - 1)];
        const to = i + 1 < starts.length ? starts[i + 1] : durationInFrames;
        if (to <= from) return null;
        return (
          <Sequence key={clip} from={from} durationInFrames={to - from} name={`BG${i}`}>
            <BackgroundPhoto src={clip} videoDurationSec={clipDurationsSec[i]} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
