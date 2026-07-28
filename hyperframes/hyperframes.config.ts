import { defineConfig } from "hyperframes";

export default defineConfig({
  width: 1080,
  height: 1920,
  fps: 30,
  output: "out/reel.mp4",
  codec: "h264",
});
