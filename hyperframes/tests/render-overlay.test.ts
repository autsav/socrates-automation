// hyperframes/tests/render-overlay.test.ts
//
// Smoke test only — actually launching Puppeteer in CI would need a Chromium
// binary. Verifies the `render` function is exported so downstream tasks
// (Task 8 pipeline.py _invoke_hyperframes) can import it.

import { describe, it, expect } from "vitest";

describe("render-overlay CLI", () => {
  it("exports a render function", async () => {
    const mod = await import("../src/cli/render-overlay");
    expect(typeof mod.render).toBe("function");
  });
});