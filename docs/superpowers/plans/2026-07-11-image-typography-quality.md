# Image & Typography Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bundle Playfair Display, make the FLUX tier configurable (default flux-pro), and persist/override image seeds — the three genuine gaps not already implemented.

**Architecture:** Task 1 bundles the font + prepends it in `_load_font`. Task 2 adds a FLUX tier map + per-tier payload builder in `image_generator.py`. Task 3 adds seed resolution + a `(Path, seed)` return. Task 4 persists the seed (schema migration + `save_post`) and wires it through `pipeline.py`.

**Tech Stack:** Python 3.11 (repo `.venv`), Pillow (variable-font weight axis), Fal.ai FLUX, sqlite3.

## Global Constraints

- **Run Python tests with the 3.11 venv:** `.venv/bin/python -m pytest …` (system python is 3.9).
- **Do NOT re-build already-implemented work:** aspect ratio, inference steps, guidance, negative prompt, prompt enhancement, adaptive font sizing, balanced wrap, brightness panel, stroke/gradient — all exist and must be left intact.
- **Font is OFL Playfair Display**, fetched from `https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/` (verified reachable: upright 300KB, italic 278KB, OFL.txt 4.4KB). Bundle `OFL.txt` (license requirement).
- **FLUX tier** default `pro` (`fal-ai/flux-pro/v1.1`), via `FAL_TIER` env; unknown tier → `pro` + warning.
- **flux-pro/v1.1 payload is the one external unknown** — verify param names against Fal.ai docs during Task 2; do not guess silently.
- Filenames contain literal brackets (`PlayfairDisplay[wght].ttf`) — **quote paths** in shell/git commands (brackets are glob chars).
- Do NOT re-commit `data/pipeline.db`; the seed-column migration applies at runtime (idempotent).
- 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures are unrelated; "green" = no NEW failures.
- **Branch:** `feat/image-typography-quality` (already checked out).

---

### Task 1: Bundle Playfair Display + load it first

**Files:**
- Create: `assets/fonts/PlayfairDisplay[wght].ttf`, `assets/fonts/PlayfairDisplay-Italic[wght].ttf`, `assets/fonts/OFL.txt`
- Modify: `src/visual/image_composer.py` (`_load_font` + module constants)
- Test: `tests/test_bundled_font.py` (NEW)

**Interfaces:**
- Produces: module constants `image_composer.BUNDLED_FONT_DIR`, `image_composer.PLAYFAIR_UPRIGHT`, `image_composer.PLAYFAIR_ITALIC` (Paths); `_load_font(size, bold=False, italic=False)` returns the bundled Playfair variable font first, with the weight axis set to 900 (bold) or 400.

- [ ] **Step 1: Fetch the fonts into the repo**

Run (quote the bracketed names):
```bash
cd "$(git rev-parse --show-toplevel)"
mkdir -p assets/fonts
base="https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay"
curl -fsSL "$base/PlayfairDisplay%5Bwght%5D.ttf"        -o "assets/fonts/PlayfairDisplay[wght].ttf"
curl -fsSL "$base/PlayfairDisplay-Italic%5Bwght%5D.ttf" -o "assets/fonts/PlayfairDisplay-Italic[wght].ttf"
curl -fsSL "$base/OFL.txt"                              -o "assets/fonts/OFL.txt"
ls -la assets/fonts/
```
Expected: three files, the two `.ttf` ~300KB/~278KB, `OFL.txt` ~4KB. If any curl fails (non-zero / tiny file), STOP and report BLOCKED (network issue) — do not fabricate a font.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_bundled_font.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw
from src.visual import image_composer as ic


def test_bundled_playfair_files_present():
    assert ic.PLAYFAIR_UPRIGHT.exists(), "bundled upright Playfair missing"
    assert ic.PLAYFAIR_ITALIC.exists(), "bundled italic Playfair missing"
    assert (ic.BUNDLED_FONT_DIR / "OFL.txt").exists(), "OFL license missing"


def test_load_font_uses_bundled_playfair_first():
    f = ic._load_font(48, bold=True)
    assert "PlayfairDisplay" in str(getattr(f, "path", "")), "should load bundled Playfair, not a system font"


def test_bold_is_heavier_than_regular():
    # Setting the weight axis to 900 must produce visibly heavier (wider) glyphs
    # than 400 — this proves the variable-font weight axis is actually applied.
    img = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(img)
    reg = ic._load_font(80, bold=False)
    bold = ic._load_font(80, bold=True)
    assert d.textlength("Wisdom", font=bold) > d.textlength("Wisdom", font=reg)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_bundled_font.py -v`
Expected: FAIL — `image_composer` has no `PLAYFAIR_UPRIGHT` / `_load_font` returns a system font.

- [ ] **Step 4: Add the bundled-font constants + prepend logic**

In `src/visual/image_composer.py`, near the top (after the imports), add:

```python
BUNDLED_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
PLAYFAIR_UPRIGHT = BUNDLED_FONT_DIR / "PlayfairDisplay[wght].ttf"
PLAYFAIR_ITALIC = BUNDLED_FONT_DIR / "PlayfairDisplay-Italic[wght].ttf"
```

Then, in `_load_font`, insert this block as the **first thing** the function does (before the existing `if bold: font_candidates = [...]` logic):

```python
    # Prefer the bundled Playfair Display variable font — consistent premium
    # typography everywhere, and never falls through to Pillow's bitmap default.
    bundled = PLAYFAIR_ITALIC if italic else PLAYFAIR_UPRIGHT
    if bundled.exists():
        try:
            f = ImageFont.truetype(str(bundled), size)
            try:
                f.set_variation_by_axes([900 if bold else 400])
            except Exception:
                pass  # non-variable build / axis unsupported — keep default instance
            return f
        except Exception:
            pass  # fall through to system fonts below
```

(Leave the entire existing system-candidate + `ImageFont.load_default()` fallback in place unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_bundled_font.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit** (quote the bracketed paths)

```bash
git add "assets/fonts/PlayfairDisplay[wght].ttf" "assets/fonts/PlayfairDisplay-Italic[wght].ttf" assets/fonts/OFL.txt src/visual/image_composer.py tests/test_bundled_font.py
git commit -m "feat(typography): bundle Playfair Display (OFL) and load it first"
```

---

### Task 2: Configurable FLUX tier + payload builder

**Files:**
- Modify: `src/visual/image_generator.py` (tier map, `_resolve_tier`, `_fal_url`, `_build_payload`)
- Test: `tests/test_fal_tier.py` (NEW)

**Interfaces:**
- Produces: `FAL_TIER_URLS` (dict), `_resolve_tier() -> str` (env `FAL_TIER`, default `"pro"`, unknown → `"pro"`), `_fal_url(tier) -> str`, `_build_payload(tier, prompt, seed) -> dict`.

- [ ] **Step 1: Verify the flux-pro/v1.1 schema**

Read the current Fal.ai docs for `fal-ai/flux-pro/v1.1` (via WebFetch on `https://fal.ai/models/fal-ai/flux-pro/v1.1` or the API schema). Confirm the accepted input params. The implementation below assumes pro accepts `prompt`, `image_size`, `num_images`, `seed`, `safety_tolerance`, `output_format`, `enable_safety_checker`, and does NOT accept `num_inference_steps`/`guidance_scale`/`negative_prompt`. If the real schema differs, adjust the `pro` branch of `_build_payload` accordingly and note the difference in your report.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_fal_tier.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visual import image_generator as ig


def test_resolve_tier_defaults_to_pro(monkeypatch):
    monkeypatch.delenv("FAL_TIER", raising=False)
    assert ig._resolve_tier() == "pro"


def test_resolve_tier_reads_env_and_rejects_unknown(monkeypatch):
    monkeypatch.setenv("FAL_TIER", "dev")
    assert ig._resolve_tier() == "dev"
    monkeypatch.setenv("FAL_TIER", "bogus")
    assert ig._resolve_tier() == "pro"


def test_fal_url_maps_tiers():
    assert ig._fal_url("pro").endswith("flux-pro/v1.1")
    assert ig._fal_url("dev").endswith("flux/dev")
    assert ig._fal_url("schnell").endswith("flux/schnell")


def test_payload_pro_omits_steps_has_safety():
    p = ig._build_payload("pro", "a prompt", 123)
    assert "num_inference_steps" not in p and "guidance_scale" not in p
    assert p.get("safety_tolerance")
    assert p["seed"] == 123 and p["image_size"] == "portrait_16_9" and p["num_images"] == 1


def test_payload_schnell_has_steps_and_guidance():
    p = ig._build_payload("schnell", "a prompt", 7)
    assert p["num_inference_steps"] and p["guidance_scale"]
    assert p["seed"] == 7
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_fal_tier.py -v`
Expected: FAIL — those functions don't exist yet.

- [ ] **Step 4: Implement the tier map + helpers**

In `src/visual/image_generator.py`, replace the line:

```python
FAL_API_URL = "https://fal.run/fal-ai/flux/schnell"
```

with:

```python
# FLUX tier map. Default "pro" for best fidelity; override with FAL_TIER env.
FAL_TIER_URLS = {
    "schnell": "fal-ai/flux/schnell",
    "dev": "fal-ai/flux/dev",
    "pro": "fal-ai/flux-pro/v1.1",
}


def _resolve_tier() -> str:
    """Pick the FLUX tier from FAL_TIER env; default and fallback = 'pro'."""
    t = os.getenv("FAL_TIER", "pro").lower()
    if t not in FAL_TIER_URLS:
        print(f"  [image] Unknown FAL_TIER={t!r} — falling back to 'pro'")
        t = "pro"
    return t


def _fal_url(tier: str) -> str:
    return f"https://fal.run/{FAL_TIER_URLS[tier]}"


def _build_payload(tier: str, prompt: str, seed: int) -> dict:
    """Emit only the params a given tier supports."""
    shared = {
        "prompt": prompt,
        "image_size": "portrait_16_9",  # 576x1024 native vertical (9:16)
        "num_images": 1,
        "seed": seed,
        "enable_safety_checker": True,
    }
    if tier == "pro":
        # flux-pro/v1.1: no steps/guidance/negative_prompt.
        return {**shared, "safety_tolerance": "5", "output_format": "jpeg"}
    # schnell / dev
    return {
        **shared,
        "negative_prompt": NEGATIVE_PROMPT,
        "num_inference_steps": 6,
        "guidance_scale": 3.5,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_fal_tier.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add src/visual/image_generator.py tests/test_fal_tier.py
git commit -m "feat(image): configurable FLUX tier (default flux-pro) + per-tier payload"
```

---

### Task 3: Seed resolution + `(Path, seed)` return

**Files:**
- Modify: `src/visual/image_generator.py` (`_resolve_seed`, `generate_background`, `__main__`)
- Test: `tests/test_image_seed.py` (NEW)

**Interfaces:**
- Consumes: `_resolve_tier`, `_fal_url`, `_build_payload` (Task 2).
- Produces: `_resolve_seed(seed=None) -> int`; `generate_background(mood, api_key, output_dir="output", quote="", anthropic_api_key="", prompt_override="", seed: int | None = None) -> tuple[Path, int]` (returns `(path, seed_used)`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_image_seed.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visual import image_generator as ig


def test_resolve_seed_prefers_explicit():
    assert ig._resolve_seed(4242) == 4242


def test_resolve_seed_reads_env(monkeypatch):
    monkeypatch.setenv("FAL_SEED", "77")
    assert ig._resolve_seed(None) == 77


def test_resolve_seed_random_in_range(monkeypatch):
    monkeypatch.delenv("FAL_SEED", raising=False)
    s = ig._resolve_seed(None)
    assert 0 <= s <= 999999


def test_generate_background_returns_path_and_seed(monkeypatch, tmp_path):
    monkeypatch.setattr(ig, "enhance_prompt", lambda *a, **k: "p")
    monkeypatch.setattr(ig, "_generate_with_retry", lambda h, p, **k: {"images": [{"url": "http://x/y.jpg"}]})

    class _Resp:
        content = b"x" * 50
        def raise_for_status(self):
            pass

    monkeypatch.setattr(ig.requests, "get", lambda *a, **k: _Resp())
    path, seed = ig.generate_background("calm_stoic", "key", output_dir=str(tmp_path), quote="q", seed=4242)
    assert seed == 4242
    assert Path(path).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_image_seed.py -v`
Expected: FAIL — `_resolve_seed` missing; `generate_background` returns a `Path`, not a tuple.

- [ ] **Step 3: Add `_resolve_seed`**

In `src/visual/image_generator.py`, add near the other helpers:

```python
def _resolve_seed(seed: int | None = None) -> int:
    """Use an explicit seed, else FAL_SEED env, else a random seed."""
    if seed is not None:
        return int(seed)
    env = os.getenv("FAL_SEED")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    return random.randint(0, 999999)
```

- [ ] **Step 4: Rewire `generate_background`**

In `src/visual/image_generator.py`, change the signature to add `seed` and the return type, and replace the seed/payload/URL section. The signature becomes:

```python
def generate_background(
    mood: str,
    api_key: str,
    output_dir: str = "output",
    quote: str = "",
    anthropic_api_key: str = "",
    prompt_override: str = "",
    seed: int | None = None,
) -> tuple[Path, int]:
```

Replace the body block that currently reads:

```python
    # Seed for reproducibility + variety
    seed = random.randint(0, 999999)

    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "image_size": "portrait_16_9",   # 576×1024 native vertical (9:16)
        "num_inference_steps": 6,          # sharper detail than 4
        "guidance_scale": 3.5,             # stronger prompt adherence
        "num_images": 1,
        "enable_safety_checker": True,
        "seed": seed,
    }

    print(f"  [image] Generating {mood} background (seed={seed}, steps=6)...")
    data = _generate_with_retry(headers, payload)
```

with:

```python
    tier = _resolve_tier()
    seed = _resolve_seed(seed)
    payload = _build_payload(tier, prompt, seed)

    print(f"  [image] Generating {mood} background (tier={tier}, seed={seed})...")
    data = _generate_with_retry(headers, payload, url=_fal_url(tier))
```

- [ ] **Step 5: Thread the tier URL into `_generate_with_retry`**

`_generate_with_retry(headers, payload, max_retries=2)` currently posts to the module `FAL_API_URL` constant, which no longer exists. Add a `url` parameter and use it. Change its signature to:

```python
def _generate_with_retry(headers, payload, max_retries=2, url="https://fal.run/fal-ai/flux-pro/v1.1"):
```

and inside it replace every `FAL_API_URL` reference with `url`.

- [ ] **Step 6: Update the final return + `__main__`**

Change the final `return filename` in `generate_background` to:

```python
    return filename, seed
```

And in the `if __name__ == "__main__":` block, unpack:

```python
    path, seed = generate_background(
        "dark_philosophical",
        os.getenv("FAL_API_KEY"),
        quote="The unexamined life is not worth living.",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    )
    print(f"Saved: {path} (seed={seed})")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_image_seed.py tests/test_fal_tier.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/visual/image_generator.py tests/test_image_seed.py
git commit -m "feat(image): seed resolution + return (path, seed); route via tier URL"
```

---

### Task 4: Persist the seed + wire through the pipeline

**Files:**
- Modify: `src/core/data_store.py` (`posts.seed` column + migration, `save_post(seed=...)`)
- Modify: `pipeline.py` (capture seed at the main image site → `save_post`; `path, _ =` at the other sites; `--seed` CLI)
- Test: `tests/test_seed_persist.py` (NEW)

**Interfaces:**
- Consumes: `generate_background(...) -> (Path, int)` (Task 3).
- Produces: `save_post(quote_text, audience, mood, caption_variant, posting_slot, dry_run=False, hook_id=None, seed=None) -> int | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_seed_persist.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import src.core.data_store as ds


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DB_PATH", tmp_path / "t.db")
    ds.init_db()
    return ds


def test_seed_column_migration_idempotent(db):
    db.init_db()  # second run must not error
    conn = db._get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(posts)")}
    conn.close()
    assert "seed" in cols


def test_save_post_persists_seed(db):
    rid = db.save_post("q", "aud", "calm_stoic", 0, 5, dry_run=True, seed=4242)
    conn = db._get_connection()
    val = conn.execute("SELECT seed FROM posts WHERE id = ?", (rid,)).fetchone()[0]
    conn.close()
    assert val == 4242
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_seed_persist.py -v`
Expected: FAIL — no `seed` column; `save_post` rejects `seed=`.

- [ ] **Step 3: Add the `seed` column + migration**

In `src/core/data_store.py`, in the `CREATE TABLE IF NOT EXISTS posts (...)`, change the last column line from:

```python
                post_date TEXT DEFAULT (date('now'))
```

to:

```python
                post_date TEXT DEFAULT (date('now')),
                seed INTEGER DEFAULT NULL
```

Then, immediately after the `post_date` migration + index block (after the `CREATE UNIQUE INDEX ... ux_posts_slot_day ...` statement), add:

```python
        # Migration: add seed (image reproducibility) to older posts tables.
        if "seed" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN seed INTEGER DEFAULT NULL")
```

- [ ] **Step 4: Add `seed` to `save_post`**

In `src/core/data_store.py`, update `save_post` — add the parameter and include it in the INSERT. The signature becomes:

```python
def save_post(
    quote_text: str,
    audience: str,
    mood: str,
    caption_variant: int,
    posting_slot: int,
    dry_run: bool = False,
    hook_id: str | None = None,
    seed: int | None = None,
) -> int | None:
```

and the INSERT becomes:

```python
        cursor.execute(
            """
            INSERT INTO posts
              (quote_text, audience, mood, caption_variant, posting_slot,
               posted_at, dry_run, hook_id, post_date, seed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'), ?)
            ON CONFLICT(post_date, posting_slot) WHERE dry_run = 0 DO NOTHING
            """,
            (quote_text, audience, mood, caption_variant, posting_slot,
             None, dry_run, hook_id, seed),
        )
```

- [ ] **Step 5: Run the data_store tests**

Run: `.venv/bin/python -m pytest tests/test_seed_persist.py tests/test_data_store_dedup.py -v`
Expected: PASS (seed tests + the existing dedup tests still green).

- [ ] **Step 6: Wire the seed through `pipeline.py`**

First read the sites: `sed -n '684,692p' pipeline.py`, `sed -n '744,758p' pipeline.py`, `sed -n '784,806p' pipeline.py`.

(a) Main image generation (~line 686) — capture the seed. Change:

```python
    image_path = generate_background(
        mood=mood,
        api_key=cfg.FAL_API_KEY,
        output_dir=OUTPUT_DIR,
        quote=quote_data["quote"],
```
so the call is assigned to a tuple and passes the CLI seed. It must become `image_path, image_seed = generate_background(... , seed=seed)` — add `seed=seed` to the kwargs and unpack the tuple. (The `seed` name refers to the `run_pipeline` parameter added in step (d).)

(b) The `save_post` call in `run_pipeline` (~line 748, the one with `caption_variant=caption_variant`) — pass the captured seed. Add `seed=image_seed,` to its kwargs.

(c) The three reel background calls (~lines 786, 795, 804, `bg_hook_path`/`bg_quote_path`/`bg_cta_path`) — they now return tuples; unpack and discard the seed. Change each `bg_X_path = generate_background(` assignment to `bg_X_path, _ = generate_background(`.

(d) Add a `--seed` CLI + thread it. In the `argparse` setup (near the other `add_argument` calls), add:

```python
    parser.add_argument("--seed", type=int, default=None, help="Force a FLUX image seed for reproducible backgrounds.")
```

Add `seed: int | None = None` to the `run_pipeline(...)` signature (after its existing params), and in the `__main__`/dispatch that calls `run_pipeline(...)`, pass `seed=args.seed`.

- [ ] **Step 7: Verify pipeline + full suite**

Run: `.venv/bin/python -c "import ast; ast.parse(open('pipeline.py').read()); print('pipeline ok')"`
Expected: `pipeline ok`

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: only the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures; no new failures.

- [ ] **Step 8: Commit**

```bash
git add src/core/data_store.py pipeline.py tests/test_seed_persist.py
git commit -m "feat(pipeline): persist image seed per post + --seed override"
```

---

## Self-Review

**Spec coverage:**
- §4.1 bundle Playfair + `_load_font` prepend + weight axis → Task 1. ✓
- §4.2 FLUX tier map + `FAL_TIER` + per-tier payload + pro schema verify → Task 2. ✓
- §4.3 `generate_background` seed param + `(Path, seed)` return + all 5 callers + `posts.seed` migration + `save_post(seed=)` + `--seed` → Tasks 3 & 4. ✓
- §7 testing (font / payload / seed / migration) → tests in Tasks 1-4. ✓
- Return-type change propagated to all 5 `generate_background` call sites (self-test __main__, main image, 3 reel bgs) → Task 3 Step 6 + Task 4 Step 6. ✓

**Placeholder scan:** No TBD/TODO. Task 2 Step 1 (verify pro schema) is a real verification step with a concrete default + instruction to adjust — not a placeholder. Every code step shows full code.

**Type consistency:** `generate_background(...) -> tuple[Path, int]` defined in Task 3, consumed in Task 4 (unpacked at every site). `_resolve_tier`/`_fal_url`/`_build_payload` names identical across Task 2 impl/tests and Task 3 usage. `_generate_with_retry(..., url=...)` new kwarg added in Task 3 Step 5 and used in Step 4. `save_post(..., seed=None)` defined in Task 4 Step 4, tested in Step 1. `seed` column name identical in schema, migration, save_post, and tests. ✓

**Ordering:** Task 2 before Task 3 (build_payload/url consumed); Task 3 before Task 4 (tuple return consumed). ✓
