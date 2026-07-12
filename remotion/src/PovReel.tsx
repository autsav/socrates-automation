import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { GradientBg } from "./components/GradientBg";
import { ParticleField } from "./components/ParticleField";
import { PulsingBg } from "./components/PulsingBg";
import { HookScene } from "./components/HookScene";
import { QuoteScene } from "./components/QuoteScene";
import { CtaScene } from "./components/CtaScene";
import { getPalette } from "./styles/theme";
import { duckVolume, DuckSpan } from "./lib/duckVolume";
import { sceneFrames } from "./lib/sceneFrames";

export { sceneFrames } from "./lib/sceneFrames";

export interface PovReelProps {
  hook: string;
  quote: string;
  attribution: string;
  cta: string;
  mood: string;
  duration: number;
  fps: number;
  beats?: number[];
  voices?: { hook?: string; quote?: string; cta?: string };
  music?: string;
  voiceDurations?: { hook?: number; quote?: number; cta?: number };
}

export const povReelDefaultProps: PovReelProps = {
  hook: "Purpose doesn't find you. You find it.",
  quote: "The beginning of wisdom is the desire to learn.",
  attribution: "— Socrates",
  cta: "Save this. You'll need it again.",
  mood: "dark_philosophical",
  duration: 10.5,
  fps: 30,
  beats: [],
  voices: {},
  music: undefined,
  voiceDurations: {},
};

/** A brief hard white flash — a pattern interrupt at each scene boundary. */
const WhiteFlash: React.FC<{ at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [at - 3, at, at + 3],
    [0, 0.85, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  if (opacity <= 0) return null;
  return (
    <AbsoluteFill
      style={{ background: "white", opacity, pointerEvents: "none" }}
    />
  );
};

export const PovReel: React.FC<PovReelProps> = ({
  hook,
  quote,
  attribution,
  cta,
  mood,
  beats = [],
  voices = {},
  music,
  voiceDurations = {},
}) => {
  const { durationInFrames, fps } = useVideoConfig();
  const palette = getPalette(mood);
  const { hook: hookF, quote: quoteF } = sceneFrames(
    durationInFrames / fps,
    fps,
    voiceDurations
  );
  const quoteEnd = hookF + quoteF;

  const spanFor = (
    start: number,
    dur: number | undefined,
    sceneLen: number
  ): DuckSpan => ({
    start,
    end: start + (dur != null ? Math.round(dur * fps) : sceneLen),
  });
  const duckSpans: DuckSpan[] = [
    spanFor(0, voiceDurations.hook, hookF),
    spanFor(hookF, voiceDurations.quote, quoteF),
    spanFor(quoteEnd, voiceDurations.cta, durationInFrames - quoteEnd),
  ];

  return (
    <AbsoluteFill style={{ background: palette.bg[0] }}>
      {/* Continuous, attention-seeking background across the whole reel. */}
      <PulsingBg palette={palette}>
        <GradientBg palette={palette} />
        <ParticleField palette={palette} />
      </PulsingBg>

      {/* Scene text, timed with Sequences. */}
      <Sequence from={0} durationInFrames={hookF} name="Hook">
        <HookScene text={hook} palette={palette} />
      </Sequence>

      <Sequence from={hookF} durationInFrames={quoteF} name="Quote">
        <QuoteScene
          quote={quote}
          attribution={attribution}
          palette={palette}
          beats={beats}
        />
      </Sequence>

      {voices.hook ? (
        <Sequence from={0} durationInFrames={hookF} name="HookVO">
          <Audio src={staticFile(voices.hook)} />
        </Sequence>
      ) : null}
      {voices.quote ? (
        <Sequence from={hookF} durationInFrames={quoteF} name="QuoteVO">
          <Audio src={staticFile(voices.quote)} />
        </Sequence>
      ) : null}
      {voices.cta ? (
        <Sequence
          from={quoteEnd}
          durationInFrames={durationInFrames - quoteEnd}
          name="CtaVO"
        >
          <Audio src={staticFile(voices.cta)} />
        </Sequence>
      ) : null}
      {music ? (
        <Audio
          src={staticFile(music)}
          volume={(f: number) => duckVolume(f, duckSpans)}
        />
      ) : null}

      <Sequence
        from={quoteEnd}
        durationInFrames={durationInFrames - quoteEnd}
        name="CTA"
      >
        <CtaScene text={cta} palette={palette} />
      </Sequence>

      {/* Pattern-interrupt flashes at the two scene boundaries. */}
      <WhiteFlash at={hookF} />
      <WhiteFlash at={quoteEnd} />
    </AbsoluteFill>
  );
};
