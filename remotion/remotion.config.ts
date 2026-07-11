import { Config } from "@remotion/cli/config";

// Output: MP4 H264, 1080x1920 vertical Instagram Reel, high quality.
Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");
Config.setPixelFormat("yuv420p");
Config.setCrf(18);
Config.setChromiumOpenGlRenderer("angle");
// Headless render — no browser window needed. Overwrite existing output.
Config.setOverwriteOutput(true);
