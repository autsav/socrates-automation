import React from "react";
import {
  AbsoluteFill,
  Img,
  Loop,
  OffthreadVideo,
  staticFile,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const VIDEO_EXTS = [".mp4", ".webm", ".mov", ".m4v"];

const isVideo = (src: string) =>
  VIDEO_EXTS.some((e) => src.toLowerCase().endsWith(e));

/** Full-bleed background — real stock footage (OffthreadVideo: deterministic
 *  server-side frames, no Html5Video delayRender timeouts) or a FLUX photo
 *  (Ken-Burns zoom) — under a dark scrim for text legibility. Footage shorter
 *  than the reel loops via <Loop> when its duration is known; otherwise it
 *  holds its last frame. */
export const BackgroundPhoto: React.FC<{ src: string; videoDurationSec?: number }> = ({
  src,
  videoDurationSec,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [1.06, 1.14], {
    extrapolateRight: "clamp",
  });
  const cover: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  };
  const video = <OffthreadVideo src={staticFile(src)} muted style={cover} />;
  const loopFrames =
    videoDurationSec && videoDurationSec > 0
      ? Math.max(1, Math.floor(videoDurationSec * fps))
      : null;
  return (
    <AbsoluteFill>
      {isVideo(src) ? (
        loopFrames ? <Loop durationInFrames={loopFrames}>{video}</Loop> : video
      ) : (
        <Img
          src={staticFile(src)}
          style={{ ...cover, transform: `scale(${scale})`, transformOrigin: "center" }}
        />
      )}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0.55) 55%, rgba(0,0,0,0.8) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
