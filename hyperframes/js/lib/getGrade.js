export const MOOD_GRADES = {
    dark_philosophical: { filter: "contrast(1.1) saturate(1.05)", vignette: 0.55 },
    dramatic_ancient: { filter: "contrast(1.12) saturate(1.1) sepia(0.08)", vignette: 0.6 },
    cinematic_hopeful: { filter: "contrast(1.06) saturate(1.15) brightness(1.03)", vignette: 0.4 },
    stark_minimal: { filter: "contrast(1.15) saturate(0.9)", vignette: 0.35 },
    epic_warrior: { filter: "contrast(1.14) saturate(1.12)", vignette: 0.55 },
    mystical_greek: { filter: "contrast(1.08) saturate(1.18) hue-rotate(-6deg)", vignette: 0.6 },
    calm_stoic: { filter: "contrast(1.04) saturate(1.06) brightness(1.02)", vignette: 0.4 },
};
const DEFAULT_GRADE = { filter: "contrast(1.08) saturate(1.1)", vignette: 0.5 };
export function getGrade(mood) {
    return (mood && MOOD_GRADES[mood]) || DEFAULT_GRADE;
}
