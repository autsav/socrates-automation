# MPT (MoneyPrinterTurbo) CLI Contract

**Date:** 2026-07-29
**MPT version:** v1.3.3 (cloned from `harry0703/MoneyPrinterTurbo@main`)
**Purpose:** Single source of truth for invoking MPT from Python without the WebUI.

---

## Invocation

**Working directory MUST be `mpt/`** — MPT's `app` package lives at repo root, not
inside `mpt/mpt/`. There is no `python -m mpt` invocation.

```bash
cd /Users/utsab1/Documents/socrates\ automation/mpt
.venv/bin/python cli.py --video-subject "..." --stop-at video
```

or equivalently:

```bash
cd /Users/utsab1/Documents/socrates\ automation/mpt
PYTHONPATH=. .venv/bin/python -m cli --video-subject "..."
```

The brief assumed `python -m mpt.main`. That pattern does NOT apply — `main.py`
runs `uvicorn` (the WebUI). The CLI is `cli.py`, not `main.py`.

## Venv

MPT's own dependencies live in `mpt/requirements.txt`. Install into
`mpt/.venv/` (separate from repo `.venv/`):

```bash
python3.11 -m venv mpt/.venv
mpt/.venv/bin/pip install -r mpt/requirements.txt
```

A copy of `config.example.toml` → `mpt/config.toml` is required for the CLI to
load; keys may be empty arrays for `--stop-at script`.

## CLI exit codes

| Code | Meaning |
|------|---------|
| 0 | Task completed for selected `--stop-at` stage |
| 1 | Task failure (any stage) |
| 2 | Argument parsing / input validation error |

On success the CLI prints exactly one JSON object to stdout:
```json
{"task_id": "<uuid>", "result": {...stage-specific...}}
```
Logs go to stderr.

## Required arguments (exactly one of)

| Flag | Type | Notes |
|------|------|-------|
| `--video-subject TEXT` | string | LLM-driven script generation |
| `--video-script TEXT` | string | Pre-written script (skips LLM script gen) |

## Pipeline stages (`--stop-at`)

Stages execute in fixed order; the CLI stops after the named stage and emits
that stage's result.

| Stage | Requires | Result JSON field |
|-------|----------|-------------------|
| `script` | subject or script | `"script"` |
| `terms` | subject (or script) | `"terms"` |
| `audio` | script + voice config | `"audio"` (path + duration) |
| `subtitle` | audio + enabled subtitles | `"subtitle"` (srt path) |
| `materials` | terms (or `--video-materials`) | `"materials"` |
| `video` | all of the above | `"videos"` (list of MP4 paths) |

Default `--stop-at` is `video` (full pipeline).

`--stop-at terms` with `--video-source local` → exit 2 (validation error).

## Core flags we will use

| Flag | Default | Notes |
|------|---------|-------|
| `--video-script TEXT` | "" | Pre-written script (preferred for our use — LLM cost) |
| `--video-source {pexels,pixabay,coverr,local}` | `pexels` | Local source requires `--video-materials` |
| `--video-aspect {9:16,16:9,1:1}` | `9:16` | Portrait for IG Reels |
| `--stop-at {script,terms,audio,subtitle,materials,video}` | `video` | Full / partial pipeline |
| `--voice-name VOICE` | `zh-CN-XiaoxiaoNeural-Female` | Use `no-voice` for silent; we provide our own VO from edge-tts |
| `--bgm-type {none,random,custom,sonilo}` | `random` | `none` for our use (we mix Jamendo separately) |
| `--bgm-volume FLOAT` | 0.2 | Per config |
| `--subtitle-enabled / --no-subtitle-enabled` | enabled | `--no-subtitle-enabled` for our use (we burn captions via ffmpeg) |
| `--video-clip-duration INT` | 5 | Max seconds per source clip |
| `--video-concat-mode {random,sequential}` | random | sequential when materials map to script order |
| `--video-transition-mode {none,shuffle,fade-in,fade-out,slide-in,slide-out}` | none | none for cleanest cut |
| `--n-threads INT` | 2 | FFmpeg worker threads |
| `--task-id UUID` | auto | Custom UUID for task dir |

## Environment / config

MPT reads `mpt/config.toml` (Tom's Original Mass), populated from
`mpt/config.example.toml` on first run. The CLI does NOT consume
`config.toml` env vars directly — settings live in the toml file.

**Required for full pipeline (`--stop-at video`):**
- `pexels_api_keys` (or pixabay/coverr keys) — non-empty list
- LLM credentials via `[llm]` provider — OpenAI / Gemini / DashScope / etc.
  (see `config.example.toml`)
- Optional: Sonilo BGM (`[sonilo]`) — `bgm_type=sonilo`

**For `--stop-at video` with `--video-source local` and `--video-materials`:**
- Only `edge_tts` voice provider — no API keys needed
- No LLM needed if `--video-script` is provided
- No material-provider keys needed (local)

## Output paths

Each task writes a working directory at:

```
mpt/storage/tasks/<task-id>/
```

Final MP4s end up under `mpt/storage/tasks/<task-id>/<n>.mp4` (one per
`--video-count`). The CLI emits the JSON result with paths; downstream code
should consume those paths rather than scan the directory.

## Smoke verification (2026-07-29)

```bash
$ cd mpt && .venv/bin/python cli.py --video-script "Test script for smoke" --stop-at script
... (logs to stderr) ...
{"task_id": "d11396cd-046d-4843-af61-6a77459328e2",
 "result": {"script": "Test script for smoke"}}
```

Exit code 0. CLI contract confirmed working.

## Smoke verification for full pipeline

NOT verified end-to-end in Task 1 because it requires Pexels API keys + LLM
key. Verification requires either (a) CI secrets or (b) a stub Pexels key for
`--video-source local`. Task 3+ will exercise the full pipeline with the
HyperFrames pipeline integration.

## `_invoke_mpt()` contract (downstream tasks)

Downstream Python code (`src/pipeline/hyperframes.py` / wrapper) should:

1. `cd` into `mpt/` (or set `cwd=` via subprocess)
2. Run `.venv/bin/python cli.py <args...>`
3. Capture stdout (JSON), stderr (logs), exit code
4. On exit 0: parse stdout JSON, expect `"result"` key
5. On exit 1 / non-zero: log stderr, raise

Recommended subprocess shape:

```python
result = subprocess.run(
    [str(MPT_VENV / "python"), "cli.py", *cli_args],
    cwd=MPT_ROOT,
    capture_output=True,
    text=True,
    timeout=600,
)
```

Use `cwd=MPT_ROOT` (absolute path to `mpt/`), not `python -m mpt`. Use
absolute paths throughout (project rule: all paths must be absolute when
invoking subprocess).