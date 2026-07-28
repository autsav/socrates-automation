export type MoodName =
  | "dark_philosophical"
  | "dramatic_ancient"
  | "cinematic_hopeful"
  | "stark_minimal"
  | "epic_warrior"
  | "mystical_greek"
  | "calm_stoic";

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
