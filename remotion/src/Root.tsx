import React from "react";
import { Composition } from "remotion";
import {
  PovReel,
  PovReelProps,
  povReelDefaultProps,
  sceneFrames,
} from "./PovReel";
import { VIDEO } from "./styles/theme";

// Sentry ErrorBoundary is intentionally NOT used here. The `import * as Sentry`
// from "@sentry/react" pattern produced undefined-ErrorBoundary at bundle time
// when bundled headless (webpack ESM/CJS interop on the namespace import), and
// the headless render path has no DSN configured anyway. sentry.ts still
// initializes Sentry as a side-effect if a DSN is ever set.
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
        povReelDefaultProps.fps,
        povReelDefaultProps.voiceDurations,
        !!povReelDefaultProps.bridge,
        !!povReelDefaultProps.hook
      ).total}
      calculateMetadata={({ props }: { props: PovReelProps }) => {
        const fps = props.fps || VIDEO.fps;
        const { total } = sceneFrames(
          props.duration || 10.5,
          fps,
          props.voiceDurations,
          !!props.bridge,
          !!props.hook
        );
        return { durationInFrames: total, fps };
      }}
    />
  );
};
