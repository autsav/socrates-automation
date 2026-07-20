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
import { BackgroundReel } from "./components/BackgroundReel";
import { HookScene } from "./components/HookScene";
import { BridgeScene } from "./components/BridgeScene";
import { QuoteScene } from "./components/QuoteScene";
import { CtaScene } from "./components/CtaScene";
import { ColorGrade } from "./components/ColorGrade";
import { FilmGrade } from "./components/FilmGrade";
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
  sfx?: { whoosh?: string; impact?: string; riser?: string; sub_impact?: string };
  wordTimes?: { hook?: WordTime[]; bridge?: WordTime[]; quote?: WordTime[]; cta?: WordTime[] };
  /** OPTIONAL fal.ai FLUX photo background (staticFile name). When set, it
   *  replaces the gradient base; the particle field renders over it. */
  background?: string;
  /** Duration of a video background in seconds (for looping). */
  backgroundDurationSec?: number;
  /** OPTIONAL multi-clip background reel — takes over from `background` when
   *  it has 2+ entries; each clip owns a segment cut at scene/stress bounds. */
  backgrounds?: string[];
  backgroundDurationsSec?: number[];
  /** OPTIONAL: seconds of leading silence trimmed from the Quote VO clip —
   *  the audio Sequence starts this much later than the visual Quote scene. */
  silenceDropSec?: number;
  /** Seed varying which per-word effect flavor (e.g. pop vs pop2) AnimatedText
   *  uses; deterministic given the seed, differs between reels (spec 3). */
  animSeed?: number;
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
  backgrounds: undefined,
  backgroundDurationsSec: undefined,
  silenceDropSec: undefined,
  animSeed: 0,
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
  backgrounds,
  backgroundDurationsSec,
  silenceDropSec,
  animSeed = 0,
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

  // Silence drop: the Quote VO clip has its leading silence trimmed, so its
  // Sequence starts `dropFrames` after the visual Quote scene begins.
  const dropFrames =
    silenceDropSec && silenceDropSec > 0 ? Math.round(silenceDropSec * fps) : 0;

  // Beats are word/beat timings relative to the Quote VO's actual start (after
  // silence drop). Offset must track the adjusted audio start: quoteStart + dropFrames.
  const beatFrames = beats.map((t) => Math.round(t * fps) + quoteStart + dropFrames);
  const scale = cameraScale(frame, durationInFrames, beatFrames);
  // Speed ramp: a quick punch-in right before the Quote lands (only when the
  // Quote isn't already at frame 0 — nothing to ramp into on a cold open).
  const speedRamp =
    quoteStart > 0
      ? interpolate(frame, [quoteStart - 12, quoteStart], [1, 1.08], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1;
  const finalScale = scale * speedRamp;

  // Multi-clip background cut points: scene starts, plus mid-bridge stress
  // cuts (7-word chunk starts from wordTimes.bridge) spaced >=3s apart,
  // clamped to one cut per clip.
  const cutFrames = React.useMemo(() => {
    if (!backgrounds || backgrounds.length < 2) return [0];
    const sceneStarts = [0, hookF, quoteStart, quoteEnd];
    const minGap = Math.round(3 * fps);
    const stressCuts: number[] = [];
    if (bridge && wordTimes.bridge && wordTimes.bridge.length) {
      const wt = wordTimes.bridge;
      let lastKept = hookF;
      for (let ci = 1; ci * 7 < wt.length; ci++) {
        const wi = ci * 7;
        const f = hookF + Math.round(wt[wi].start * fps);
        if (f - lastKept >= minGap) {
          stressCuts.push(f);
          lastKept = f;
        }
      }
    }
    const all = Array.from(new Set([...sceneStarts, ...stressCuts])).sort(
      (a, b) => a - b
    );
    return all.slice(0, backgrounds.length);
  }, [backgrounds, hookF, quoteStart, quoteEnd, bridge, wordTimes.bridge, fps]);

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

  // Music is forced near-silent across the silence-drop gap (a beat of true
  // silence reads as more dramatic than a duck), and an optional riser/sub-impact sell the cut.
  const musicVolume = (f: number) => {
    if (dropFrames > 0 && f >= quoteStart && f <= quoteStart + dropFrames) {
      return 0.02;
    }
    return duckVolume(f, duckSpans);
  };
  const firstQuoteBeat = beatFrames.find((bf) => bf >= quoteStart);
  const subImpactFrame =
    firstQuoteBeat !== undefined ? firstQuoteBeat : quoteStart + dropFrames;

  // Quote beats/wordTimes, shifted for the silence-drop gap — shared by the
  // real Quote scene and its ghost-trail echo below.
  const quoteBeats =
    dropFrames > 0 && beats.length > 0
      ? beats.map((t) => t + (silenceDropSec ?? 0))
      : beats;
  const quoteWordTimes =
    dropFrames > 0 && wordTimes.quote && wordTimes.quote.length > 0
      ? wordTimes.quote.map((wt) => ({
          ...wt,
          start: wt.start + (silenceDropSec ?? 0),
          end: wt.end + (silenceDropSec ?? 0),
        }))
      : wordTimes.quote;

  // Ghost-trail (spec 3): a faint, drifting echo of the Quote scene's own
  // opening frames, previewed just before it lands — only when the Quote
  // isn't a cold open (quoteStart > 0) and only within the 12-frame ramp
  // window right before it.
  const showGhostTrail =
    quoteStart > 0 && frame >= quoteStart - 12 && frame < quoteStart;

  const ctaVoEndFrame = voiceDurations.cta
    ? Math.round(voiceDurations.cta * fps)
    : undefined;

  return (
    <AbsoluteFill style={{ background: palette.bg[0] }}>
      <ColorGrade grade={getGrade(mood)}>
        <FilmGrade>
        <AbsoluteFill style={{ transform: `scale(${finalScale})` }}>
          {/* Continuous background across the whole reel. A multi-clip reel
              (2+ backgrounds) cuts on scene/stress bounds; a single FLUX photo
              replaces the gradient base; particles ride over any of them. */}
          {backgrounds && backgrounds.length >= 2 ? (
            <>
              <BackgroundReel
                clips={backgrounds}
                clipDurationsSec={backgroundDurationsSec ?? []}
                cutFrames={cutFrames}
              />
              <ParticleField palette={palette} />
            </>
          ) : background ? (
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
              <HookScene text={hook} palette={palette} wordTimes={wordTimes.hook} animSeed={animSeed} />
            </Sequence>
          ) : null}

          {bridge ? (
            <Sequence from={hookF} durationInFrames={bridgeF} name="Bridge">
              <BridgeScene text={bridge} palette={palette} wordTimes={wordTimes.bridge} animSeed={animSeed} />
            </Sequence>
          ) : null}

          {showGhostTrail ? (
            <div
              style={{
                position: "absolute",
                inset: 0,
                opacity: 0.3,
                transform: `translateY(${(quoteStart - frame) * 0.8}px)`,
                pointerEvents: "none",
              }}
            >
              <Sequence from={quoteStart - 12} durationInFrames={12} name="QuoteGhost">
                <QuoteScene
                  quote={quote}
                  attribution={attribution}
                  palette={palette}
                  beats={quoteBeats}
                  wordTimes={quoteWordTimes}
                  staticFirstFrames={0}
                />
              </Sequence>
            </div>
          ) : null}

          <Sequence from={quoteStart} durationInFrames={quoteF} name="Quote">
            <QuoteScene
              quote={quote}
              attribution={attribution}
              palette={palette}
              beats={quoteBeats}
              wordTimes={quoteWordTimes}
              staticFirstFrames={quoteStart === 0 ? 3 : 0}
            />
          </Sequence>

          <Sequence
            from={quoteEnd}
            durationInFrames={durationInFrames - quoteEnd}
            name="CTA"
          >
            <CtaScene text={cta} palette={palette} voEndFrame={ctaVoEndFrame} />
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
                <HookScene text={hook} palette={palette} wordTimes={wordTimes.hook} animSeed={animSeed} />
              </LoopFadeIn>
            </Sequence>
          ) : null}
        </AbsoluteFill>
        </FilmGrade>
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
        <Sequence from={quoteStart + dropFrames} durationInFrames={quoteF} name="QuoteVO">
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
        <Audio src={staticFile(music)} volume={musicVolume} />
      ) : null}
      {sfx.riser && silenceDropSec ? (
        <Sequence
          from={Math.max(0, quoteStart - 36)}
          durationInFrames={36}
          name="Riser"
        >
          <Audio src={staticFile(sfx.riser)} volume={0.3} />
        </Sequence>
      ) : null}
      {sfx.sub_impact ? (
        <Sequence from={subImpactFrame} durationInFrames={12} name="SubImpact">
          <Audio src={staticFile(sfx.sub_impact)} volume={0.4} />
        </Sequence>
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
