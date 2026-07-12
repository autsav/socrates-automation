import React from "react";
import { AbsoluteFill } from "remotion";
import { Grade } from "../styles/theme";

const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

/** Cinematic finish: a CSS filter on the content, plus a vignette and a subtle
 *  film-grain overlay. Wrap only the VISUAL layers. */
export const ColorGrade: React.FC<{ grade: Grade; children: React.ReactNode }> = ({ grade, children }) => (
  <AbsoluteFill>
    <AbsoluteFill style={{ filter: grade.filter }}>{children}</AbsoluteFill>
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,${grade.vignette}) 100%)`,
        pointerEvents: "none",
      }}
    />
    <AbsoluteFill
      style={{ background: GRAIN, opacity: 0.06, mixBlendMode: "overlay", pointerEvents: "none" }}
    />
  </AbsoluteFill>
);
