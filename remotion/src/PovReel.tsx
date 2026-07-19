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
import { BackgroundPhoto } from "./components/BackgroundPhoto";
import { HookScene } from "./components/HookScene";
import { BridgeScene } from "./components/BridgeScene";
import { QuoteScene } from "./components/QuoteScene";
import { CtaScene } from "./components/CtaScene";
import { ColorGrade } from "./components/ColorGrade";
import { getPalette, getGrade } from "./styles/theme";
import { duckVolume, DuckSpan } from "./lib/duckVolume";
import { sceneFrames } from "./lib/sceneFrames";
import { cameraScale } from "./lib/cameraZoom";
import { WordTime } from "./lib/wordAt";

export { sceneFrames } from "./lib/sceneFrames";

// `type` (not `interface`): a closed type alias is assignable to
// `Record<string, unknown>`, which Remotion's <Composition> requires of its
// component props. An interface is not (it can be augmented via declaration
// merging), which is what caused the Root.tsx TS2322 errors.
export type PovReelProps = {
  hook: string;
  quote: string;
  attribution: string;
  cta: string;
  mood: string;
  duration: number;
  fps: number;
  beats?: number[];
  /** OPTIONAL Bridge scene — the pivot from the trending Hook into the timeless
   *  Quote. Rendered only when non-empty (Hook -> Bridge -> Quote -> CTA);
   *  empty (the default) renders the original 3-scene Hook -> Quote -> CTA arc. */
  bridge?: string;
  voices?: { hook?: string; bridge?: string; quote?: string; cta?: string };
  music?: string;
  voiceDurations?: { hook?: number; bridge?: number; quote?: number; cta?: number };
  sfx?: { whoosh?: string; impact?: string };
  wordTimes?: { hook?: WordTime[]; bridge?: WordTime[]; quote?: WordTime[]; cta?: WordTime[] };
  /** OPTIONAL fal.ai FLUX photo background (staticFile name). When set, it
   *  replaces the gradient base; the particle field renders over it. */
  background?: string;
  /** Duration of a video background in seconds (for looping). */
  backgroundDurationSec?: number;
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
  bridge: "",
  voices: {},
  music: undefined,
  voiceDurations: {},
  sfx: {},
  wordTimes: {},
  background: undefined,
  backgroundDurationSec: undefined,
};

/** Fades its children in across the loop-preview window. */
const LoopFadeIn: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const f = useCurrentFrame();
  const opacity = interpolate(f, [0, 12], [0, 0.9], {
    extrapolateRight: "clamp",
  });
  return <div style={{ position: "absolute", inset: 0, opacity }}>{children}</div>;
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
  bridge = "",
  voices = {},
  music,
  voiceDurations = {},
  sfx = {},
  wordTimes = {},
  background,
  backgroundDurationSec,
}) => {
  const { durationInFrames, fps } = useVideoConfig();
  const palette = getPalette(mood);
  const { hook: hookF, bridge: bridgeF, quote: quoteF } = sceneFrames(
    durationInFrames / fps,
    fps,
    voiceDurations,
    !!bridge,
    !!hook
  );
  const quoteStart = hookF + bridgeF;
  const quoteEnd = quoteStart + quoteF;

  const frame = useCurrentFrame();
  // Beats are word/beat timings relative to the Quote scene's own start, so the
  // offset must track wherever Quote actually begins (hookF, or hookF+bridgeF
  // once a Bridge is inserted) — not a fixed hookF.
  const beatFrames = beats.map((t) => Math.round(t * fps) + quoteStart);
  const scale = cameraScale(frame, durationInFrames, beatFrames);

  const spanFor = (
    start: number,
    dur: number | undefined,
    sceneLen: number
  ): DuckSpan => ({
    start,
    end: start + (dur != null ? Math.round(dur * fps) : sceneLen),
  });
  const duckSpans: DuckSpan[] = [
    ...(hook ? [spanFor(0, voiceDurations.hook, hookF)] : []),
    ...(bridge ? [spanFor(hookF, voiceDurations.bridge, bridgeF)] : []),
    spanFor(quoteStart, voiceDurations.quote, quoteF),
    spanFor(quoteEnd, voiceDurations.cta, durationInFrames - quoteEnd),
  ];

  return (
    <AbsoluteFill style={{ background: palette.bg[0] }}>
      <ColorGrade grade={getGrade(mood)}>
        <AbsoluteFill style={{ transform: `scale(${scale})` }}>
          {/* Continuous background across the whole reel. A FLUX photo replaces
              the gradient base when supplied; particles ride over either. */}
          {background ? (
            <>
              <BackgroundPhoto src={background} videoDurationSec={backgroundDurationSec} />
              <ParticleField palette={palette} />
            </>
          ) : (
            <PulsingBg palette={palette}>
              <GradientBg palette={palette} />
              <ParticleField palette={palette} />
            </PulsingBg>
          )}

          {/* Scene text, timed with Sequences. The Hook is OPTIONAL — a
              cold-open arc drops it so the Quote hits at frame 0. */}
          {hook ? (
            <Sequence from={0} durationInFrames={hookF} name="Hook">
              <HookScene text={hook} palette={palette} wordTimes={wordTimes.hook} />
            </Sequence>
          ) : null}

          {bridge ? (
            <Sequence from={hookF} durationInFrames={bridgeF} name="Bridge">
              <BridgeScene text={bridge} palette={palette} wordTimes={wordTimes.bridge} />
            </Sequence>
          ) : null}

          <Sequence from={quoteStart} durationInFrames={quoteF} name="Quote">
            <QuoteScene
              quote={quote}
              attribution={attribution}
              palette={palette}
              beats={beats}
              wordTimes={wordTimes.quote}
              staticFirstFrames={quoteStart === 0 ? 3 : 0}
            />
          </Sequence>

          <Sequence
            from={quoteEnd}
            durationInFrames={durationInFrames - quoteEnd}
            name="CTA"
          >
            <CtaScene text={cta} palette={palette} />
          </Sequence>

          {/* Pattern-interrupt flashes at each scene boundary: hook->bridge (or
              hook->quote when there's no bridge), bridge->quote (only when a
              Bridge is present — otherwise quoteStart === hookF and this would
              double up the flash above), and quote->cta. */}
          {hook ? <WhiteFlash at={hookF} /> : null}
          {bridge ? <WhiteFlash at={quoteStart} /> : null}
          <WhiteFlash at={quoteEnd} />

          {/* Seamless-loop preview (recipe #4): the final 12 frames crossfade
              toward the opening composition so replay feels continuous and
              average watch time can exceed 100%. */}
          {hook ? (
            <Sequence
              from={Math.max(0, durationInFrames - 12)}
              durationInFrames={12}
              name="LoopPreview"
            >
              <LoopFadeIn>
                <HookScene text={hook} palette={palette} wordTimes={wordTimes.hook} />
              </LoopFadeIn>
            </Sequence>
          ) : null}
        </AbsoluteFill>
      </ColorGrade>

      {hook && voices.hook ? (
        <Sequence from={0} durationInFrames={hookF} name="HookVO">
          <Audio src={staticFile(voices.hook)} />
        </Sequence>
      ) : null}
      {bridge && voices.bridge ? (
        <Sequence from={hookF} durationInFrames={bridgeF} name="BridgeVO">
          <Audio src={staticFile(voices.bridge)} />
        </Sequence>
      ) : null}
      {voices.quote ? (
        <Sequence from={quoteStart} durationInFrames={quoteF} name="QuoteVO">
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
      {sfx.whoosh ? (
        <>
          {hook ? (
            <Sequence from={hookF} durationInFrames={12} name="WhooshQuote">
              <Audio src={staticFile(sfx.whoosh)} volume={0.35} />
            </Sequence>
          ) : null}
          <Sequence from={quoteEnd} durationInFrames={12} name="WhooshCta">
            <Audio src={staticFile(sfx.whoosh)} volume={0.35} />
          </Sequence>
        </>
      ) : null}
      {sfx.impact
        ? beatFrames.map((bf, i) => (
            <Sequence key={`impact-${i}`} from={bf} durationInFrames={8} name={`Impact${i}`}>
              <Audio src={staticFile(sfx.impact!)} volume={0.28} />
            </Sequence>
          ))
        : null}
    </AbsoluteFill>
  );
};
