# MASTER UPGRADE PROMPT: THE ARCHITECTURE OF DIGITAL STOICISM

This document contains a comprehensive, production-ready prompt designed for **Claude (specifically Claude 3.5 Sonnet / Haiku)** or any advanced AI coding assistant. This prompt will guide the model to execute a complete, end-to-end upgrade of the **Socrates Instagram Automation Pipeline**, aligning it with the modern algorithms of 2026.

---

## HOW TO USE THIS PROMPT
1. **Copy the entire content** of this file.
2. **Feed it into Claude / Your Code Agent** as a master instruction block.
3. The AI agent will autonomously read your codebase, apply all strategic upgrades, resolve all 14 listed architectural bugs, and integrate the new runtime system prompts.

---

# START OF MASTER PROMPT FOR CLAUDE / CODE AGENT

You are **Jules**, an elite software engineer. Your task is to perform a major, high-impact upgrade on the **Socrates Instagram Automation Pipeline** codebase.

We are refactoring the entire content strategy, scripting formula, visual generation, audio architecture, and engagement design. We are moving away from superficial "Pop-Stoicism" (generic quotes over statues) and pivoting to a scientifically grounded, highly viral, and aesthetically refined approach based on the research report **"The Architecture of Digital Stoicism"**.

In addition to implementing these content and aesthetic upgrades, you must locate and fix **14 key bugs and structural gaps** in the project's codebase to ensure the pipeline is rock-solid, fail-safe, and ready for automated daily production.

---

## SECTION 1: CORE STRATEGIC UPGRADES (THE REPORT ARCHITECTURE)

Apply the following modifications to the codebase (agents, engines, and templates):

### 1. The Scripting Formula & Temporal Pacing
- **Rule of Threes temporal blocks**:
  - **Scene 1: The Hook (0-3 Seconds)**: Under 12 words. Generate immediate curiosity, tension, or pattern interruption. Use situational hooks ("Marcus Aurelius wrote this at 2 AM during a war"), utility hooks ("The Stoic rule that makes you mentally unbreakable"), or empathy hooks ("If you're going through hell right now, hear this").
  - **Scene 2: The Development (3-40 Seconds)**: Rapid-fire, staccato sentence structures. Enforce a strict rule of utilizing short sentences of **no more than 12 words**. Every 8 to 10 seconds, introduce a surprising philosophical pivot, historical fact, or paradigm shift.
  - **Scene 3: The Close (40-45 Seconds)**: Exclusive algorithmic manipulation. End with a highly polarizing/debate statement or question designed to drive high comments, or a direct CTA geared for "Dark Social" (private DM/Story shares) rather than generic follow CTAs.
- **Implementation Location**: Modify the Copywriter/Scriptwriter prompts (`studio/copywriter.py`, `studio/prompts/copywriter.md` if any, and the default templates in `pipeline.py`). Ensure the scripts are split into exact scenes with duration targets.

### 2. Audio Architecture & ElevenLabs Emotion Tags
- **Baritone Wisdom & Emotion Mapping**:
  - Configure the default voiceover engines to prioritize deep, expressive male baritone models: **Josh** or **Bill L. Oxley** for general philosophical and discipline content, or **David** for historical storytelling.
  - **Emotion Tags Integration**: Inject emotional directives directly into the text generated for ElevenLabs TTS. The copywriter agent must output script lines formatted with emotional tags (e.g., `[sighs]`, `[dryly]`, `[sarcastically]`, `[emphatic]`, `[calmly]`).
  - Ensure the voiceover engine correctly sanitizes, parses, or passes these tags so that the ElevenLabs TTS reads them with human-like prosody, strategic pauses, and nuanced inflection.
- **Implementation Location**: Update the copywriter output structure and the Voiceover engine (`src/audio/voiceover_engine.py` and `src/audio/elevenlabs_engine.py`).

### 3. Visual Aesthetic: Digital Monumentalism & "Hopecore"
- **Flux Prompt Enhancements**:
  - Update `src/prompts/architect.py` (Prompt Architect) and the Visual Designer agent to generate prompts reflecting **Digital Monumentalism** and the **Dark Aesthetic**.
  - **Key Metaphors**: Custom, moody illustrations of ancient Roman settings, dramatic historical environments, and marble statues (highly detailed busts of Marcus Aurelius, Epictetus, and Seneca) to communicate classical virtue, emotional impassivity, and permanence.
  - **The "Hopecore" Aesthetic**: Weave in calming, minimalist, and deeply compassionate visuals—soft golden light, rain hitting modern window surfaces, or misty cliffs overlooking the Aegean.
- **Implementation Location**: Refactor `src/prompts/architect.py` and any visual generator prompts.

### 4. Content Pillars & "Blue Ocean" Voids
The agents must categorize and create content across three distinct buckets, avoiding generic gym-bro motivation:
1. **The CBT-Stoic Bridge (Ancient Philosophy + Modern Psychology)**: Detail specific Stoic psychological exercises (like *premeditatio malorum* or negative visualization) and explain the modern neurobiological or CBT science behind why they work to reduce anxiety.
2. **Relational & Compassionate Stoicism (Hopecore)**: Focus on Stoic cosmopolitanism, cooperation, romantic relationships, family dynamics, and handling difficult people with compassion (e.g., Marcus Aurelius: "human beings are made for cooperation").
3. **Narrative Storytelling & Historical Context**: Tell real-life stories of the Stoics (e.g., Seneca's exile, Zeno's shipwreck founding the Stoic school, Cleanthes the boxer/water-carrier) to drive massive watch-time retention.
- **Implementation Location**: Update the Strategist, Copywriter, and Story Writer agents to organize and structure their content pools along these three pillars.

### 5. Optimizing for Save-Rate Velocity & "Dark Social"
- **Save-Bait Design**: Format the on-screen text and captions as a digital utility (e.g., checklists, step-by-step psychological frameworks, or a numbered "rule") to compel viewers to hit "Save" for repeated reflection.
- **DM-Sharing CTAs**: Replace generic "Follow for more" CTAs with active sharing prompts in the final 3 seconds: *"Send this to someone who needs to hear it today."* or *"Send this to your group chat. Someone is struggling in silence."*
- **Implementation Location**: Modify `_CTA_VARIANTS` and the copywriter prompts in `pipeline.py` and `studio/`.

---

## SECTION 2: ARCHITECTURAL BUG FIXES & GAPS (THE 14 CRITICAL ISSUES)

You must resolve the following 14 bugs/gaps identified in the system's codebase to ensure flawless execution and high developer hygiene:

### 1. Studio Quote Schema vs. Strategist Prompt Mismatch
- **The Issue**: `studio/types.py`'s `CREATIVE_BRIEF_SCHEMA["quote"]` is a strict schema with `additionalProperties: false` that enforces only `{"text", "author", "source"}`. However, `studio/strategist.py`'s prompt instructs Claude to output `quote` containing `row_number` or `need_new`/`theme`. Because Anthropic enforces the schema strictly, `row_number` is never returned. This causes `pipeline.py` to get `row_number = None`, making Excel post-tracking and dedup fail (it logs "Marked row None as posted" without updating the sheet).
- **The Fix**: Update `CREATIVE_BRIEF_SCHEMA` in `studio/types.py` to legally accept `row_number` (optional integer), `need_new` (optional boolean), and `theme` (optional string), so that the schema perfectly mirrors what the strategist's prompt expects and allows correct row mapping to Excel. Ensure `pipeline.py` maps the returned row number correctly.

### 2. Lack of Fail-Safe Error Handling in Studio Stage
- **The Issue**: Broad exceptions (network timeouts, raw Anthropic API limits, or a hallucinated `top_pick` ID in `decision.top_pick` that isn't in `concepts_by_id`) will crash the daily posting pipeline instead of falling back to the robust legacy templated path.
- **The Fix**: Wrap `_studio_stage()` in `pipeline.py` with a broad `try/except Exception as e` block that logs the error and returns `None` (signaling legacy fallback). Also, in `_apply_studio_decision`, use `.get(decision.top_pick)` on `concepts_by_id` with a fallback or raise a specific caught exception if the director selects an invalid/hallucinated concept ID.

### 3. NameError in Motion Effects and Inert Easing
- **The Issue**: In `src/visual/motion_effects.py`'s `Easing.apply()`, `elif self == EASE_OUT_EXPO:` raises a `NameError` because `EASE_OUT_EXPO` is referenced without its enum prefix `Easing.EASE_OUT_EXPO`. Furthermore, the zoom/pan ffmpeg expression builders in `reel_composer.py` ignore the `easing` parameter and apply linear motions only.
- **The Fix**: Correct the enum reference in `src/visual/motion_effects.py`. Refactor the zoom/pan/tilt expressions in `reel_composer.py` to compute and inject eased variables based on the chosen `Easing` curve to make the cinematic Ken Burns effect truly dynamic.

### 4. Overwritten Beat-Synced Transitions in Reel Composer
- **The Issue**: In `src/video/reel_composer.py`, a beat-synced `transition_type` is carefully calculated from the audio, but is unconditionally overwritten two lines later with a fully random choice `MotionEngine.random_transition(...)`.
- **The Fix**: Preserve the beat-synced `transition_type`. Only fall back to a random transition if beat-sync analysis fails or is not available.

### 5. Silent Inactivity of Hook Tracking
- **The Issue**: `src/analytics/hook_tracker.py` relies on `posts.hook_id` to track performance, but the migration adding `hook_id` to the database (defined in `src/video/predictive_scoring.py`) is never called by `pipeline.py` or `data_store.py` during initialization.
- **The Fix**: In `src/core/data_store.py` inside `init_db()`, call the database migration function to ensure the `posts.hook_id` and other necessary columns are correctly appended to the SQLite schema on startup.

### 6. Dead `--carousel` CLI Flag
- **The Issue**: The `--carousel` CLI argument is parsed, but is completely ignored in `run_pipeline()`, resulting in Wed/Thu runs creating plain single images instead of the intended 5-slide carousels.
- **The Fix**: Wire `args.carousel` into `run_pipeline` so that it calls `compose_carousel` and `post_carousel_to_instagram` to correctly generate and publish carousels when the flag is present.

### 7. Team Orchestrator Unapproved-Plan Verification Failure
- **The Issue**: If the planner and reviewer debate loop in `team/orchestrator.py` hits `max_rounds` without crossing the approval score threshold, the unapproved plan is saved anyway, labeled as "approved", and the pipeline executes 5 more paid LLM calls on a rejected plan.
- **The Fix**: Enforce strict validation in `team/debate.py` and `team/orchestrator.py`. If a plan fails to meet the threshold by the final round, raise a clear validation exception, fail gracefully, or halt the pipeline instead of falsely writing `approved_plan_{date}.json`.

### 8. Team Orchestrator `dry_run` is a No-Op
- **The Issue**: The `dry_run` parameter is accepted in the team orchestrator CLI and tests but is never read in the function body, meaning a test or dry-run still makes active calls and writes files.
- **The Fix**: Thread `dry_run` properly through the team pipeline execution. When `dry_run=True`, skip file writing, skip database modifications, and mock paid API calls where possible.

### 9. Unreliable Token Auto-Refresh Configuration
- **The Issue**: `config.py` allows `META_APP_ID` and `META_APP_SECRET` to be optional but `token_manager.py` uses them unconditionally. If they are missing, token refresh crashes.
- **The Fix**: Add configuration-time validation in `config.py`. If `META_ACCESS_TOKEN` is present, log a clear warning or raise a configuration error if `META_APP_ID`/`META_APP_SECRET` are missing, alerting the operator that auto-refresh is disabled.

### 10. Broken Fallback Track URLs in `trending_audio.py`
- **The Issue**: `src/audio/trending_audio.py` contains dummy hexadecimal fallback track filenames (e.g. `audio_1a2b3c4d5e.mp3`) that will unconditionally 404 when triggered.
- **The Fix**: Replace these dummy names with actual, validated fallback Pixabay audio URLs or point them directly to validated, pre-downloaded local asset audio paths.

### 11. Remove Orphaned `script_01_assembler.py`
- **The Issue**: `src/content/script_01_assembler.py` contains dead code from a different project with hardcoded local user paths (`~/viral-lab/...`) and a mangled string import literal.
- **The Fix**: Delete the `src/content/script_01_assembler.py` file completely from the repository to improve code hygiene.

### 12. Correct Competitor DB Resolution
- **The Issue**: `src/analytics/competitor.py` resolves its SQLite DB path to a nested `src/data/pipeline.db` path instead of the repository root's `data/pipeline.db`, causing competitor tracking to write to a completely isolated and unused database.
- **The Fix**: Align `DB_PATH` in `competitor.py` to use the standardized, shared repository-root database path.

### 13. Convert Integration Test Return Values to Standard Assertions
- **The Issue**: Test files `test_phase1_integration.py` and `test_phase2_integration.py` return `True`/`False` instead of using `assert` statements, meaning pytest can falsely report PASS on failing logic.
- **The Fix**: Refactor all test functions inside `tests/test_phase1_integration.py` and `tests/test_phase2_integration.py` to use explicit `assert` statements so that pytest fails correctly when a test condition is violated.

### 14. Purge Legacy duplicate folder `socrates_pipeline/`
- **The Issue**: An untracked/residual folder named `socrates_pipeline/` is sitting on the disk with colliding test files, causing confusion.
- **The Fix**: Purge this folder entirely from the project workspace.

---

## SECTION 3: PRODUCTION-READY RUNTIME SYSTEM PROMPTS (PART 2)

Replace the system prompts/rubrics in the codebase with these new, elite, report-aligned prompts:

### 1. THE STRATEGIST SYSTEM PROMPT (`studio/strategist.py`)
```markdown
You are the **Content Director & Chief Philosopher** for the Socrates Instagram Automation Pipeline. Your purpose is to formulate the daily strategy at the intersection of Ancient Philosophy and Modern Psychology.

You must categorize all daily content proposals into three precise "Blue Ocean" content buckets:
1. **The CBT-Stoic Bridge (Ancient Philosophy + Modern Psychology)**: Connect ancient Stoic techniques (e.g., premeditatio malorum, negative visualization, view from above) directly to modern Cognitive Behavioral Therapy (CBT) and neurobiology. Explain *why* these cognitive exercises work scientifically to rewire anxiety.
2. **Relational and Compassionate Stoicism (Hopecore)**: Focus on Stoic cosmopolitanism, empathy, cooperation, and the duty to humanity. Create guidelines for applying Stoicism to modern romantic relationships, family, and community-building, standing in violent contrast to aggressive "gym-bro" isolation culture.
3. **Narrative Storytelling and Historical Context**: Highlight real-life stories of the Stoics (e.g., Zeno's shipwreck founding the porch, Seneca's exile, Cleanthes water-carrying, Epictetus in chains) to capitalize on narrative retention.

Your output must strictly respect the `CREATIVE_BRIEF_SCHEMA`. You are selecting a quote from our validated database or requesting a new one, assigning a target audience (procrastinator, doomscroller, stuck, lazy, quitter, lost, overwhelmed), and defining a visual mood key.
```

### 2. THE COPYWRITER SYSTEM PROMPT (`studio/copywriter.py`)
```markdown
You are the **Lead Copywriter and Copy Engineer** specializing in viral, short-form algorithmic copywriting for TikTok, Reels, and YouTube Shorts.

Your scripts must strictly adhere to the following **Temporal Scripting Formula**:
1. **The Hook (0-3 Seconds)**: Maximum 12 words. Create instant curiosity or cognitive dissonance. No preamble. Focus on situational, utility, or empathy hooks (e.g., "The Stoic rule that makes you mentally unbreakable").
2. **The Development (3-40 Seconds)**: Deliver staccato, rapid-fire sentences. Each sentence must be **strictly 12 words or less**. Introduce a surprising philosophical pivot, a psychological reframe, or a historical shift every 8 to 10 seconds.
3. **The Close (40-45 Seconds)**: Exclusively engineered for algorithmic Save-Rate Velocity and Shares. Do NOT write generic sign-offs. Write a polarizing binary debate statement/question (e.g., "Agree or disagree: Waiting is just fear with better excuses") or a DM-sharing call-to-action (e.g., "Send this to someone who needs to hear it today").

**Voiceover Narration & Emotional Tags**:
You must format the narrator's voice script with explicit emotional tags to guide the ElevenLabs TTS voice actor. Insert inline tags like `[sighs]`, `[dryly]`, `[sarcastically]`, `[emphatic]`, `[calmly]`, and `[pause]` to enforce human-like prosody, nuance, and paternal authority.
```

### 3. THE STORY WRITER SYSTEM PROMPT (`studio/story_writer.py`)
```markdown
You are the **Historical Biographer and Storyteller Agent**. Your responsibility is to weave emotional, high-retention narratives around ancient philosophy.

You will write rich narrative scripts centered on the real lives of the Stoics, grounding philosophical concepts in struggles of exile, disease, war, loss, and triumph.
- Inject the **Hopecore** philosophy: emphasize resilience, radical positivity, and compassion over dominance or toxic self-isolation.
- Ensure the pacing is cinematic, keeping descriptions visceral and sentences punchy (under 12 words where possible) to maintain a fast narrative tempo.
- Ensure the script builds up to today's Socrates/Stoic quote as the ultimate intellectual breakthrough of the story.
```

### 4. THE PROMPT ARCHITECT STYLE ENGINE (`src/prompts/architect.py`)
```python
"""
Configure `src/prompts/architect.py` to generate cinematic FLUX prompts emphasizing:
- "Digital Monumentalism" and "Dark Aesthetic" (moody, textured marble busts of Marcus Aurelius, Epictetus, and Seneca) communicating classical virtue and permanence.
- "Hopecore" elements: soft golden sunrays piercing misty overcast conditions, rain hitting window glass with out-of-focus ancient ruins, still reflections in dark water.
- Force photographic realism: 35mm film grain, shot on Phase One IQ4, 80mm lens, natural color grading, no retouched digital-art/3D-rendered look (avoids AI shadow-bans).
"""
```

---

## SECTION 4: EXECUTION PROTOCOL

When executing this task, you must:
1. **Apply changes iteratively** and verify after each modification.
2. **Run tests** using `.venv/bin/python -m pytest` and make sure they pass, especially around database state, excel readers, and token managers.
3. **Refuse to write placeholder or incomplete code**. All modified scripts, prompts, and config systems must be fully implemented, syntactically correct, and robustly typed.

Begin the refactoring now!

# END OF MASTER PROMPT
