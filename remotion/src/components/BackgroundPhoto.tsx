import React from "react";
import {
  AbsoluteFill,
  Img,
  Video,
  staticFile,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const VIDEO_EXTS = [".mp4", ".webm", ".mov", ".m4v"];

const isVideo = (src: string) =>
  VIDEO_EXTS.some((e) => src.toLowerCase().endsWith(e));

/** Full-bleed background — real stock footage (video, looped, muted) or a FLUX
 *  photo (Ken-Burns zoom) — under a bottom-weighted dark scrim so the animated
 *  text stays legible over it. */
export const BackgroundPhoto: React.FC<{ src: string }> = ({ src }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // Slow Ken-Burns zoom for stills; footage already moves, so no zoom there.
  const scale = interpolate(frame, [0, durationInFrames], [1.06, 1.14], {
    extrapolateRight: "clamp",
  });
  const cover: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  };
  return (
    <AbsoluteFill>
      {isVideo(src) ? (
        <Video src={staticFile(src)} muted loop style={cover} />
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
