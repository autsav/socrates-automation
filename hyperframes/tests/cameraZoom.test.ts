import { describe, it, expect } from "vitest";
import { cameraScale } from "../js/lib/cameraZoom";

describe("cameraScale", () => {
  it("pushes in slowly over the reel", () => {
    expect(cameraScale(300, 300, [])).toBeGreaterThan(cameraScale(0, 300, []));
  });
  it("kicks on a beat then decays", () => {
    const base = cameraScale(100, 300, []);
    const onBeat = cameraScale(100, 300, [100]);
    const afterBeat = cameraScale(105, 300, [100]);
    expect(onBeat).toBeGreaterThan(base);
    expect(afterBeat).toBeLessThan(onBeat);
  });
});
