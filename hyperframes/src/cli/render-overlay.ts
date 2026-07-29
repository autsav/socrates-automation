#!/usr/bin/env node
/**
 * HyperFrames render-overlay CLI — frame-by-frame Puppeteer capture of a
 * transparent-background overlay HTML → ffmpeg MP4 with alpha.
 *
 * Usage:
 *   npx hyperframes render-overlay --input output/run-42/overlay.html --output out/overlay.mp4
 *   npx hyperframes render-overlay                         # defaults below
 *
 * Input contract (per Task 6 brief + Task 5 template design):
 *   --input is a path RELATIVE to the hyperframes package root, pointing at a
 *   Jinja2-RENDERED .html file (not a .j2 template). The HTML embeds its own
 *   `#overlay-data` JSON, references `css/overlay.css` and `js/overlay-main.js`
 *   via root-relative paths, and exposes `(window as any).__timelines.overlay`
 *   after `overlay-main.ts` runs.
 *
 * Output contract:
 *   MP4 with `-c:v png -pix_fmt rgba` — alpha preserved for compositing on
 *   top of a base video in Task 7 (`scripts/composite_overlay.sh`).
 *
 * Defaults (override via flags):
 *   --input         output/overlay.html
 *   --output        out/overlay.mp4
 *   --fps           30
 *   --width         1080
 *   --height        1920
 *   --duration      0  (0 = auto-detect from master timeline)
 */
import puppeteer from "puppeteer-core";
import { spawn } from "child_process";
import { createServer } from "http";
import { readFileSync, mkdirSync, existsSync } from "fs";
import { resolve, dirname, extname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
// src/cli/render-overlay.ts → ../../ = hyperframes package root
const ROOT = resolve(__dirname, "../..");

const DEFAULT_INPUT = resolve(ROOT, "output/overlay.html");
const DEFAULT_OUTPUT = resolve(ROOT, "out/overlay.mp4");

function parseArgs(argv: string[]): Record<string, string> {
  const args: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const val = argv[i + 1] && !argv[i + 1].startsWith("-") ? argv[++i] : "true";
      args[key] = val;
    }
  }
  return args;
}

/**
 * Static HTTP server rooted at the hyperframes package. Serves css/, js/,
 * templates/, output/, etc. so that an input HTML at e.g. /output/run-X/overlay.html
 * can fetch `css/overlay.css` and `js/overlay-main.js` via root-relative paths.
 */
function startStaticServer(root: string, port = 0): Promise<{ url: string; stop: () => void }> {
  const server = createServer((req, res) => {
    const urlPath = (req.url || "/").split("?")[0];
    const filePath = resolve(root, "." + urlPath);
    // Path-traversal guard: refuse any request that escapes root.
    if (!filePath.startsWith(resolve(root))) {
      res.writeHead(403); res.end("Forbidden"); return;
    }
    try {
      const data = readFileSync(filePath);
      const ext = extname(filePath).toLowerCase();
      const mime: Record<string, string> = {
        ".html": "text/html", ".js": "application/javascript",
        ".css": "text/css", ".json": "application/json",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".mp4": "video/mp4",
      };
      res.writeHead(200, { "Content-Type": mime[ext] || "application/octet-stream" });
      res.end(data);
    } catch {
      res.writeHead(404); res.end("Not found");
    }
  });
  return new Promise((res) => {
    server.listen(port, "127.0.0.1", () => {
      const addr = server.address();
      const url = typeof addr === "string" ? addr : `http://127.0.0.1:${addr?.port}`;
      res({ url, stop: () => server.close() });
    });
  });
}

/**
 * Render an overlay HTML to an alpha-channel MP4.
 *
 * @param args CLI args (already parsed by `parseArgs`). See file header for keys.
 */
export async function render(args: Record<string, string>): Promise<void> {
  // --input is relative to ROOT (the hyperframes package root). Pass an
  // absolute path to override — we resolve relative paths against ROOT.
  const rawInput = args.input || DEFAULT_INPUT;
  const inputHtml = resolve(ROOT, rawInput);
  const output = args.output ? resolve(args.output) : DEFAULT_OUTPUT;
  const fps = Math.max(1, Math.min(60, parseInt(args.fps || "30", 10)));
  const width = Math.max(360, Math.min(2160, parseInt(args.width || "1080", 10)));
  const height = Math.max(640, Math.min(3840, parseInt(args.height || "1920", 10)));
  const durationSec = parseFloat(args.duration || "0");

  if (!existsSync(inputHtml)) {
    throw new Error(`Input HTML not found: ${inputHtml}`);
  }
  if (!inputHtml.endsWith(".html")) {
    throw new Error(`Input must be a rendered .html file (got ${inputHtml}). Jinja2 templates (.j2) must be pre-rendered by Python (Task 8 _invoke_hyperframes).`);
  }

  mkdirSync(dirname(output), { recursive: true });

  const server = await startStaticServer(ROOT);
  // Path relative to ROOT for the URL.
  const inputRel = inputHtml.slice(ROOT.length).replace(/^\/+/, "");
  const inputUrl = `${server.url}/${inputRel}`;

  console.log(`[overlay] Launching ${width}x${height} @ ${fps}fps (transparent BG, alpha output)`);
  console.log(`[overlay] Input URL: ${inputUrl}`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--use-gl=swiftshader"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  try {
    await page.goto(inputUrl, { waitUntil: "networkidle2" });

    // Wait for overlay-main.ts to expose __timelines.overlay (Task 5 contract).
    await page.waitForFunction(
      () => {
        const w = window as unknown as { gsap?: unknown; __timelines?: { overlay?: { duration?: () => number } } };
        return !!(w.gsap && w.__timelines && w.__timelines.overlay);
      },
      { timeout: 15000 },
    );

    const totalDur: number = durationSec > 0
      ? durationSec
      : await page.evaluate(() => {
          const tl = (window as unknown as { __timelines: { overlay: { duration: () => number } } }).__timelines.overlay;
          return tl.duration();
        });

    const totalFrames = Math.ceil(totalDur * fps);
    console.log(`[overlay] Rendering ${totalFrames} frames (${totalDur.toFixed(2)}s)`);

    // PNG-in-MP4 with alpha: PNG codec + rgba pix_fmt preserves transparency for
    // compositing in Task 7 (scripts/composite_overlay.sh uses ffmpeg overlay filter).
    // NOTE: yuv420p (used by render.ts) discards alpha — explicitly NOT used here.
    const ffmpeg = spawn(
      "ffmpeg",
      [
        "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-r", String(fps),
        "-i", "-",
        "-c:v", "png",
        "-pix_fmt", "rgba",
        "-movflags", "+faststart",
        output,
      ],
      { stdio: ["pipe", "inherit", "inherit"] },
    );

    // Swallow EPIPE / other stdin errors so a mid-stream ffmpeg crash doesn't
    // surface as an unhandled rejection. The 'close' handler below will
    // surface the ffmpeg exit code as the canonical error.
    ffmpeg.stdin!.on("error", () => {});

    let frame = 0;
    const startTime = Date.now();

    for (let i = 0; i < totalFrames; i++) {
      const t = i / fps;
      await page.evaluate((time: number) => {
        const tl = (window as unknown as { __timelines: { overlay: { time: (n: number) => void; pause: () => void } } }).__timelines.overlay;
        tl.time(time);
        tl.pause();
      }, t);

      // Allow layout/paint to settle before screenshot.
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(r)));

      // omitBackground:true is REQUIRED — the page body has `background: transparent`
      // (overlay.html.j2 line 15) and we need the screenshot to preserve that alpha.
      const png = await page.screenshot({ type: "png", omitBackground: true });
      // Guard against ffmpeg crashing mid-stream — write returns false / throws
      // EPIPE on a broken pipe. Catch and surface via the close handler.
      try {
        ffmpeg.stdin!.write(png);
      } catch {
        break;
      }

      frame++;
      if (frame % 30 === 0 || frame === totalFrames) {
        const elapsed = (Date.now() - startTime) / 1000;
        const rate = frame / Math.max(elapsed, 0.001);
        const remaining = (totalFrames - frame) / rate;
        process.stdout.write(
          `\r[overlay] ${frame}/${totalFrames}  ${((frame / totalFrames) * 100).toFixed(1)}%  ETA ${remaining.toFixed(0)}s`,
        );
      }
    }

    ffmpeg.stdin!.end();
    await new Promise<void>((res, rej) => {
      ffmpeg.on("close", (code) => {
        if (code === 0) res();
        else rej(new Error(`ffmpeg exited ${code}`));
      });
    });

    console.log(`\n[overlay] Saved ${output}`);
  } finally {
    // Tear down Chromium subprocess + bound HTTP port on every exit path.
    // `server.stop()` is synchronous-ish and idempotent; browser.close() is
    // async and idempotent — wrap its rejection so a second close (e.g. after
    // an already-closed browser) doesn't mask the original error.
    await browser.close().catch(() => {});
    server.stop();
  }
}

// CLI entry guard — only run when this file is invoked directly, not when
// imported (e.g. by tests/render-overlay.test.ts).
if (import.meta.url === `file://${process.argv[1]}`) {
  render(parseArgs(process.argv.slice(2))).catch((e: unknown) => {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[overlay] Render failed:", msg);
    process.exit(1);
  });
}