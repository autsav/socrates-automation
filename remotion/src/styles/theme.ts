/**
 * Mood color system for the POV Reel.
 *
 * Each mood maps to a Remotion-friendly palette:
 *  - bg:        3-stop radial gradient [outer, core, outer] — the animated field
 *  - text:      main text fill (huge, bold, centered)
 *  - stroke:    high-contrast outline drawn behind text for legibility
 *  - accent:    attribution / underline / CTA accent
 *  - glow:      text-shadow glow color that pulses
 *  - particles: 3 particle tints that drift upward over the field
 *  - dark:      true when the field is dark (white-ish text); false for light fields
 *
 * Colors mirror src/visual/brand_design.py MOOD_PALETTES so image + video match.
 */

export type MoodName =
  | "dark_philosophical"
  | "dramatic_ancient"
  | "cinematic_hopeful"
  | "stark_minimal"
  | "epic_warrior"
  | "mystical_greek"
  | "calm_stoic";

export interface Palette {
  bg: [string, string, string];
  text: string;
  stroke: string;
  accent: string;
  glow: string;
  particles: [string, string, string];
  dark: boolean;
}

export const MOOD_PALETTES: Record<MoodName, Palette> = {
  dark_philosophical: {
    bg: ["#0a0805", "#2a1f12", "#0a0805"],
    text: "#f5f0e8",
    stroke: "#000000",
    accent: "#c9a96e",
    glow: "#ffd78c",
    particles: ["#c9a96e", "#ffd78c", "#8b7556"],
    dark: true,
  },
  dramatic_ancient: {
    bg: ["#140a06", "#3a1d0f", "#140a06"],
    text: "#fff8eb",
    stroke: "#000000",
    accent: "#dc5f32",
    glow: "#ff8c5a",
    particles: ["#dc5f32", "#ff8c5a", "#a04628"],
    dark: true,
  },
  cinematic_hopeful: {
    bg: ["#060e18", "#153554", "#060e18"],
    text: "#ffffff",
    stroke: "#001022",
    accent: "#64b4ff",
    glow: "#96d2ff",
    particles: ["#64b4ff", "#96d2ff", "#3a6ea0"],
    dark: true,
  },
  stark_minimal: {
    bg: ["#e6e6e6", "#f6f6f6", "#e6e6e6"],
    text: "#141414",
    stroke: "#ffffff",
    accent: "#1e1e1e",
    glow: "#b0b0b0",
    particles: ["#1e1e1e", "#5a5a5a", "#909090"],
    dark: false,
  },
  epic_warrior: {
    bg: ["#140808", "#3a120e", "#140808"],
    text: "#fff5eb",
    stroke: "#000000",
    accent: "#dc3c28",
    glow: "#ff6446",
    particles: ["#dc3c28", "#ff6446", "#8b281a"],
    dark: true,
  },
  mystical_greek: {
    bg: ["#0a0618", "#2c1948", "#0a0618"],
    text: "#f5f0ff",
    stroke: "#000000",
    accent: "#b478ff",
    glow: "#d2aaff",
    particles: ["#b478ff", "#d2aaff", "#7850b4"],
    dark: true,
  },
  calm_stoic: {
    bg: ["#0e140f", "#233228", "#0e140f"],
    text: "#fafaf5",
    stroke: "#000000",
    accent: "#8cbe8c",
    glow: "#b4dcb4",
    particles: ["#8cbe8c", "#b4dcb4", "#5a8c5a"],
    dark: true,
  },
};

export const DEFAULT_MOOD: MoodName = "dark_philosophical";

export function getPalette(mood: string | undefined): Palette {
  if (mood && mood in MOOD_PALETTES) {
    return MOOD_PALETTES[mood as MoodName];
  }
  return MOOD_PALETTES[DEFAULT_MOOD];
}

// ── Typography ──────────────────────────────────────────────────────────────
// System-safe heavy stack so the render never blocks on a missing web font.
export const FONT_FAMILY =
  '"Archivo Black", "Helvetica Neue", Helvetica, Arial, sans-serif';

export const VIDEO = {
  width: 1080,
  height: 1920,
  fps: 30,
} as const;

// ── Color grade ─────────────────────────────────────────────────────────────
// Per-mood cinematic finish: a CSS filter plus a vignette darkness (0..1).

export interface Grade {
  filter: string;
  vignette: number; // 0..1 darkness at the edges
}

export const MOOD_GRADES: Partial<Record<MoodName, Grade>> = {
  dark_philosophical: { filter: "contrast(1.1) saturate(1.05)", vignette: 0.55 },
  dramatic_ancient: { filter: "contrast(1.12) saturate(1.1) sepia(0.08)", vignette: 0.6 },
  cinematic_hopeful: { filter: "contrast(1.06) saturate(1.15) brightness(1.03)", vignette: 0.4 },
  stark_minimal: { filter: "contrast(1.15) saturate(0.9)", vignette: 0.35 },
  epic_warrior: { filter: "contrast(1.14) saturate(1.12)", vignette: 0.55 },
  mystical_greek: { filter: "contrast(1.08) saturate(1.18) hue-rotate(-6deg)", vignette: 0.6 },
  calm_stoic: { filter: "contrast(1.04) saturate(1.06) brightness(1.02)", vignette: 0.4 },
};

const DEFAULT_GRADE: Grade = { filter: "contrast(1.08) saturate(1.1)", vignette: 0.5 };

export function getGrade(mood: string | undefined): Grade {
  return (mood && MOOD_GRADES[mood as MoodName]) || DEFAULT_GRADE;
}
