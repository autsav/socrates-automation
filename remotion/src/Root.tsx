import React from "react";
import { Composition } from "remotion";
import {
  PovReel,
  PovReelProps,
  povReelDefaultProps,
  sceneFrames,
} from "./PovReel";
import { VIDEO } from "./styles/theme";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="PovReel"
      component={PovReel}
      defaultProps={povReelDefaultProps}
      // 1080x1920 vertical Instagram Reel.
      width={VIDEO.width}
      height={VIDEO.height}
      // Duration + fps are driven by the props JSON the Python pipeline writes,
      // so the composition length matches the requested reel duration exactly.
      fps={povReelDefaultProps.fps}
      durationInFrames={sceneFrames(
        povReelDefaultProps.duration,
        povReelDefaultProps.fps
      ).total}
      calculateMetadata={({ props }: { props: PovReelProps }) => {
        const fps = props.fps || VIDEO.fps;
        const { total } = sceneFrames(props.duration || 10.5, fps);
        return { durationInFrames: total, fps };
      }}
    />
  );
};
