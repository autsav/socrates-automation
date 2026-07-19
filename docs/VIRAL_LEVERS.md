# VIRAL_LEVERS.md — 100 Ways This Pipeline Gets More Viral

*Researched 2026-07-19 (sources at bottom). Each lever: mechanism → impact (H/M/L) →
effort (S/M/L) → pipeline component → how the A/B loop measures it → status.*

**Status legend:** ✅ SHIPPED · 🔨 SHIPPED-THIS-WAVE · 📋 BACKLOG (optimizer queue) · ⛔ BLOCKED

**The three ranking signals everything serves (Mosseri-confirmed):**
**watch time · sends-per-reach (3–5× likes weight; >2% strong, >3% viral) · likes-per-reach.**

---

## A. Hook & Retention (watch time)

1. **First-frame text** — feed thumbnail is frame 1; blank frame = no tap. H/S — Remotion `staticFirstFrames` — measure feed CTR proxy (reach curve). 🔨
2. **Big-type ≤4-word chunks** — oversized text chunks hold the 3-second window. H/S — HookScene chunking — 3s-hold via retention graph. 🔨
3. **Statement hooks, not questions** — questions cost 0.5s retention (cognitive load). H/S — story_writer validator rejects `?` hooks — arc bandit: `question` arc vs others. 🔨
4. **Hook ≤12–15 words** — scannable in one fixation. H/S — `_enforce_hook_len` + validator. ✅
5. **Dead-air trim** — inter-scene silence kills retention; PAD 0.6→0.35s. M/S — sceneFrames. 🔨
6. **Retention > runtime** — 10s @80% beats 60s @30%; target ≤35s stories, ~14s cold-opens. H/S — duration budgets. 🔨
7. **Seamless loop** — end crossfades into the opening; replays push watch time >100%. H/S — PovReel LoopPreview. 🔨
8. **Hook must pay off** — undelivered teases cause mid-skip the algorithm punishes. H/S — copywriter prompt rule. ✅
9. **Cold-open arc** — the payoff at 0:00 as pattern interrupt. M/S — arc rotation. ✅
10. **Beat-synced camera punches** — motion spikes at emphasis moments re-grab attention. M/M — beats/impact sfx. ✅
11. **White-flash scene cuts** — hard pattern interrupts at boundaries. M/S — WhiteFlash. ✅
12. **Word-level karaoke text** — text synced to VO holds readers+listeners simultaneously. H/M — wordTimes reveal. ✅
13. **Mid-reel micro-cliffhanger** — "but that's not the weird part" before the twist. M/S — story_writer prompt addition. 📋
14. **Numbers in hooks** — "705 books", "24 hours straight" concretize curiosity. M/S — prompt nudge. 📋
15. **Negative-space framing** — "nobody tells you…" outperforms positive claims. M/S — hook pools already lean negative. ✅
16. **Progress bar illusion** — subtle time-remaining cue reduces abandonment. L/M — Remotion overlay. 📋
17. **First-word shock** — open on the strangest word of the hook. L/S — prompt nudge. 📋
18. **Retention-ordered beats** — strongest material at 0s and ~70% mark (dip point). M/S — story_writer beat guidance. 📋
19. **3-frame flash-forward** — 0.1s glimpse of the payoff before the hook. M/M — Remotion pre-roll. 📋
20. **Silence beat before the quote** — 0.4s of nothing makes the payoff land. L/S — sceneFrames gap tuning. 📋

## B. Sends & Shares (the 3–5× signal)

21. **Send-framed CTAs** — "Send this to your most stubborn friend" names the recipient. H/S — weird arc mandatory send-CTA. 🔨
22. **Weird-history capsules** — "no way this is real" is the #1 DM trigger. H/M — weird_stories pool. 🔨
23. **Relatable-callout content** — "the friend who snoozes 4 times" makes tagging inevitable. H/S — capsule send_ctas name friend archetypes. 🔨
24. **Screenshot-worthy frames** — a single frame that works as a standalone image gets shared as one. M/S — quote scene already is. ✅
25. **"Tag someone" variants** — tag CTAs rotate with send CTAs. M/S — CTA pool. ✅
26. **Group-chat bait** — content that settles an argument friends actually have (debate topics). H/S — debate pool. 🔨
27. **Identity flags** — "this is so you" content people share to describe themselves. M/M — audience-keyed capsules. 📋
28. **Useful-forward framing** — "save this for the next time you…" utility shares. M/S — CTA pool. ✅
29. **Story-resharable design** — bold central composition survives the Story-reshare crop. M/S — layout already centered. ✅
30. **Controversy that splits 50/50** — arguments in comments = reach; sends to recruit allies. H/S — debate-bait. 🔨

## C. Discovery & SEO

31. **Caption keyword SEO** — IG is a search engine; keyword captions ≈ +30% reach. H/S — `_seo_line` per audience. 🔨
32. **≤8-word curiosity first line** — pre-fold caption line drives expands (an engagement signal). M/S — `_enforce_caption_gap`. 🔨
33. **3–5 niche hashtags only** — stuffing is dead. M/S — clamp. ✅
34. **One topical tag on trend content** — rides the trend's search volume. M/S — trend_tag append. 🔨
35. **Trend-jack <24h** — recency is the multiplier. H/S — recency-first fetch_trends. 🔨
36. **Keyword-front-loaded captions** — first 125 chars indexed heaviest. M/S — gap line + SEO line ordering. 📋
37. **Alt-text keywords** — media alt text is indexed. L/S — Graph `alt_text` param. 📋
38. **On-screen text matches search terms** — OCR indexing of reels text. M/S — hooks already keyworded. ✅
39. **Consistent niche vocabulary** — repeated terms teach the algorithm your cluster. M/S — SEO pool consistency. 🔨
40. **Bio keyword optimization** — "Short resets for people rebuilding discipline" (see Positioning, below). M/S — manual step. 📋

## D. Trend & Story Content

41. **Trend-first storytelling** — the reel is ABOUT the story; quote lands as twist. H/M — story arc. 🔨
42. **Debate topics as evergreen trends** — controversy pool when news is quiet. H/S — debate fallback. 🔨
43. **Topic-matched footage** — visuals ride the story's world, not just mood. M/S — topic_query→Pexels. 🔨
44. **Contrarian reframes** — "everyone's panicking about the wrong thing." H/S — story prompt. 🔨
45. **Never-named-individuals guard** — edge without defamation risk. H/S — safety_guards. 🔨
46. **Weird-history moat** — no other stoic account mines Diogenes Laertius for absurdity. H/M — capsule pool. 🔨
47. **Hypotheticals flagged as imagination** — bizarre without misinformation. M/S — hypothetical flag. 🔨
48. **Trend→timeless bridge formula** — "…but 2,400 years ago" pivot. H/S — bridge machinery. ✅
49. **Multi-trend source redundancy** — Google Trends + GNews + Reddit. M/M — trend_sources. ✅
50. **Story beats ≤90 spoken words** — trend content must stay tight. M/S — validator budget. 🔨

## E. Visual & Audio

51. **Real footage over AI-look** — algorithm suppresses detectable AI visuals. H/S — Pexels priority. ✅
52. **Human-quality narration** — ElevenLabs; TTS monotone is the #1 quality tell. H/S — EL primary, edge-tts fallback. ✅
53. **Narration prosody arc** — urgent hook → deep quote payoff. M/S — SCENE_PROSODY. ✅
54. **Mood-matched music beds** — emotional congruence holds viewers. M/S — music director. ✅
55. **Music ducking under VO** — speech clarity. M/S — duckVolume. ✅
56. **Loudness normalization @48kHz** — platform-legal audio at social loudness. M/S — loudnorm -14 LUFS. ✅
57. **Impact SFX on emphasis words** — audio punctuation re-grabs attention. M/S — emphasis beats. ✅
58. **Whoosh transitions** — scene changes feel produced. L/S — sfx. ✅
59. **Grain + vignette color grade** — film texture reads premium. L/S — ColorGrade. ✅
60. **Trending-audio overlay** — IG-native trending sounds boost distribution; API can't attach them. ⛔ (manual-post-only feature; documented)
61. **Caption-off legibility** — 85% watch muted; full meaning without sound. H/S — text-first design. ✅
62. **4K source downscale** — sharper 1080 output. L/M — Pexels quality picker. 📋
63. **Distinct visual per scene** — footage change at quote scene. M/M — per-scene backgrounds. 📋
64. **Gold brand consistency** — instant feed recognition compounds follows. M/S — palette. ✅

## F. Engagement Mechanics

65. **First-comment debate question** — comments carry arguments; caption stays clean. H/S — first_comment. 🔨
66. **Comment triggers ("RESET")** — keyword comments double as funnel entries. H/S — trigger system. ✅
67. **First-hour reply burst** — engagement bot answers early comments; velocity signal. H/M — engagement_bot. ✅
68. **Reply-to-comments-with-reels** — replying to a comment with a follow-up reel. M/M — 📋
69. **Binary either/or CTAs** — lowest-friction comment format. H/S — debate binary_cta. 🔨
70. **Micro-surveys** — "score yourself 1–10" comment bait. M/S — CTA pool addition. 📋
71. **Pin the hottest take** — pinning a spicy comment fuels the thread. M/S — Graph pin API. 📋
72. **Ask-to-save framing** — "you'll need this Thursday" save trigger. M/S — CTA pool. ✅
73. **DM-keyword automation** — full ManyChat-style DM funnel. M/M — ⛔ (needs app review / 3rd party)
74. **Carousel save-bait** — checklists/frameworks drive saves. M/M — carousel slots exist; content upgrade. 📋

## G. Algorithm & Timing

75. **Consistency ≥5/week** — 3/day cron far exceeds. H/S — daily_post. ✅
76. **Slot-optimized posting** — 8/15/18 UTC research-backed slots. M/S — cron. ✅
77. **Original-only content** — no watermarks/recycling (exclusion criterion). H/S — by construction. ✅
78. **Trial reels** — test on non-followers first. M/M — ⛔ until 1k followers.
79. **Don't delete underperformers** — deletion hurts account signals; archive instead. L/S — policy note. 🔨(documented)
80. **Profile-grid coherence** — cover frames tell one visual story. L/M — cover frame selection. 📋
81. **Post-cadence jitter** — exact-same-second posting looks botlike. L/S — cron minute offsets. 📋
82. **Cross-format mix** — reels + carousels + (later) stories feed different surfaces. M/M — partially ✅, stories 📋
83. **Early-signal watchdog** — if reach curve is dead at 1h, first-comment a booster question. M/M — 📋
84. **Account warm-up pacing** — new accounts ramp 1→3 posts/day gradually. L/S — n/a (already ramped). ✅

## H. Psychology

85. **Curiosity gap** — open loops compel completion. H/S — hooks/captions. ✅/🔨
86. **Pattern interrupt** — violated expectations stop thumbs. H/S — weird arc + flashes. 🔨
87. **Identity challenge** — "you are the exploit" implicates the viewer. M/S — story prompt tone. 🔨
88. **Social proof numbers** — "705 books", "2,400 years" borrowed authority. M/S — capsules carry them. 🔨
89. **Loss framing** — "what it's costing you" beats "what you'd gain". M/S — stance seeds. 🔨
90. **POV framing** — "POV: you finally stopped waiting". M/S — hook variant for bandit. 📋
91. **Specificity beats abstraction** — "2am scroll" not "bad habits". M/S — prompts enforce modern-concrete. ✅
92. **The 70% dip twist** — bizarre escalation placed at the retention dip. M/S — beat guidance. 📋
93. **Earned aphorism** — the quote only after the story earns it. H/S — twist structure. 🔨
94. **Parasocial consistency** — one recognizable narrator voice. M/S — single EL voice. ✅

## I. Meta & Learning

95. **Arc-level A/B (bandit)** — posts.arc + engagement → learn which structure wins. H/M — recorded now; bandit next. 🔨/📋
96. **Prompt evolution loop** — critic proposes, humans approve, champions rotate. H/M — optimizer. ✅
97. **Sends-per-reach tracking** — the north-star metric in the reward function. H/S — reward.py includes shares; per-arc split 📋
98. **Lever-as-experiment discipline** — one lever at a time through the A/B loop, else learning goes blind. H/S — this catalog is the queue. 🔨
99. **Funnel conversion telemetry** — trigger-comments → bio → Gumroad as the money metric. M/M — funnel_log + Gumroad stats. ✅
100. **Weekly self-review** — weekly_brief digests what won; feed to strategist. M/S — analytics. ✅

---

## Positioning (manual, 1 minute)
Bio → **"Short resets for people rebuilding discipline."** Pillars: ① trend/debate stories with a Stoic twist ② weird philosophy history ③ the 3-line reset (funnel). Niche specificity gives the algorithm a cluster and viewers a reason to follow.

## Sources
[Hootsuite](https://blog.hootsuite.com/instagram-algorithm/) · [Later](https://later.com/blog/how-instagram-algorithm-works/) · [Dataslayer/Mosseri signals](https://www.dataslayer.ai/blog/instagram-algorithm-2025-complete-guide-for-marketers) · [Socialync sends](https://www.socialync.io/blog/instagram-shares-algorithm-complete-guide-2026) · [TrueFuture caption SEO](https://www.truefuturemedia.com/articles/instagram-reach-2026-algorithm-reels-carousels-caption-seo) · [OpusClip hooks](https://www.opus.pro/blog/instagram-reels-hook-formulas) · [Fobet retention](https://fobetmedia.com/instagram-reel-hooks/) · [Toptal SEO](https://www.toptal.com/creator/post/instagram-seo) · [Stan faceless](https://stan.store/blog/faceless-account/) · [Flowshorts niches](https://flowshorts.app/blog/best-niches-for-faceless-reels)
