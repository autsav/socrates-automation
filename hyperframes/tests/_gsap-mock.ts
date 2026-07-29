// Shared GSAP mock for Vitest (Node-only environment).
//
// Real GSAP calls `document.querySelectorAll` for string selectors, which
// throws in Node because `document` is undefined. This mock keeps enough of
// the timeline API surface for structural assertions (labels, accumulated
// duration) without touching the DOM.
//
// Usage at the top of a test file:
//   vi.mock("gsap", async () => (await import("./_gsap-mock")).default);
//
// Tests use this to verify timeline STRUCTURE only — real DOM/CSS execution
// happens in Puppeteer (Task 6).

import { vi } from "vitest";

interface MockTimeline {
  _labels: Record<string, number>;
  _currentEnd: number;
  addLabel: (name: string, t: number) => MockTimeline;
  to: (
    target: unknown,
    vars: { duration?: number; [k: string]: unknown },
    position?: number | string,
  ) => MockTimeline;
  from: (
    target: unknown,
    vars: { duration?: number; [k: string]: unknown },
    position?: number | string,
  ) => MockTimeline;
  fromTo: (
    target: unknown,
    fromVars: unknown,
    toVars: { duration?: number; [k: string]: unknown },
    position?: number | string,
  ) => MockTimeline;
  duration: () => number;
  labels: Record<string, number>;
}

function makeTimeline(): MockTimeline {
  const tl: MockTimeline = {
    _labels: {},
    _currentEnd: 0,
    addLabel(name, t) {
      this._labels[name] = t;
      // A label can extend the timeline if it points past the current end.
      if (t > this._currentEnd) this._currentEnd = t;
      return this;
    },
    to(_target, vars, position) {
      const dur = vars?.duration ?? 0;
      const start = typeof position === "number" ? position : this._currentEnd;
      const end = start + dur;
      if (end > this._currentEnd) this._currentEnd = end;
      return this;
    },
    from(_target, vars, position) {
      const dur = vars?.duration ?? 0;
      const start = typeof position === "number" ? position : this._currentEnd;
      const end = start + dur;
      if (end > this._currentEnd) this._currentEnd = end;
      return this;
    },
    fromTo(_target, _fromVars, toVars, position) {
      const dur = toVars?.duration ?? 0;
      const start = typeof position === "number" ? position : this._currentEnd;
      const end = start + dur;
      if (end > this._currentEnd) this._currentEnd = end;
      return this;
    },
    duration() {
      return this._currentEnd;
    },
    get labels() {
      return this._labels;
    },
  };
  return tl;
}

const gsapMock = {
  default: "gsapMock",
  timeline: () => makeTimeline(),
  to: (_target: unknown, _vars?: unknown, _position?: number | string) =>
    makeTimeline(),
  from: (_target: unknown, _vars?: unknown, _position?: number | string) =>
    makeTimeline(),
  fromTo: (
    _target: unknown,
    _fromVars?: unknown,
    _toVars?: unknown,
    _position?: number | string,
  ) => makeTimeline(),
  set: () => undefined,
  defaults: () => undefined,
};

export default gsapMock;

// Re-export `vi.mock` factory shape so callers can do:
//   vi.mock("gsap", async () => (await import("./_gsap-mock")).default);
export const __esModule = true;
export const vi_ = vi;
