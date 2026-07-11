import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
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

export interface PovReelProps {
  hook: string;
  quote: string;
  attribution: string;
  cta: string;
  mood: string;
  duration: number;
  fps: number;
}

export const povReelDefaultProps: PovReelProps = {
  hook: "Purpose doesn't find you. You find it.",
  quote: "The beginning of wisdom is the desire to learn.",
  attribution: "— Socrates",
  cta: "Save this. You'll need it again.",
  mood: "dark_philosophical",
  duration: 10.5,
  fps: 30,
};

/** Split the total duration into hook / quote / cta scene lengths (in frames).
 *  Hook and CTA get fixed budgets; the quote (the payoff) takes the remainder. */
export function sceneFrames(durationSec: number, fps: number) {
  const total = Math.round(durationSec * fps);
  const hook = Math.min(Math.round(3.5 * fps), Math.round(total * 0.34));
  const cta = Math.min(Math.round(2.5 * fps), Math.round(total * 0.26));
  const quote = Math.max(total - hook - cta, Math.round(2 * fps));
  return { total: hook + quote + cta, hook, quote, cta };
}

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
}) => {
  const { durationInFrames, fps } = useVideoConfig();
  const palette = getPalette(mood);
  const { hook: hookF, quote: quoteF } = sceneFrames(
    durationInFrames / fps,
    fps
  );
  const quoteEnd = hookF + quoteF;

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
        <QuoteScene quote={quote} attribution={attribution} palette={palette} />
      </Sequence>

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
