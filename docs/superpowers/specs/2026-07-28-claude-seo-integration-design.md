# Claude-SEO Integration — Landing Page + Audit (Sub-Project 1 of 2)

**Date:** 2026-07-28
**Status:** Design approved, awaiting spec review then plan
**Author:** Claude (brainstorming session)
**Repo (target):** https://github.com/AgricIDaniel/claude-seo

## Goal

Build a minimal local-first Astro marketing site that serves the Socrates Instagram brand across four surfaces (IG-follow CTA, email lead capture, post portfolio, AI-citable answer hub), then run `claude-seo`'s `/seo audit` against the live `astro dev` server and iterate on the findings. Site is auto-generated from `quotes.xlsx` for SEO volume; one sibling sub-project, no coupling to `pipeline.py` or `studio/`.

A second sub-project (port SEO concepts into IG content pipeline proper) is deferred to its own brainstorm cycle.

## Non-Goals (YAGNI)

- Deploying to a real host (local-only for now; defer hosting decision)
- Buying a domain
- User accounts, sessions, comments
- On-site analytics (defer until post-deploy)
- A/B testing
- Replacing or modifying `pipeline.py` / `studio/` / `remotion/`
- Building a web UI for human review (Formspree handles email capture)
- Hand-writing pillar pages at scale (auto-generation from xlsx + Astro content collections)
- Blog CMS (Phase 2 if GEO signals warrant)
- Multi-language / hreflang beyond `en`

## Architecture

### Project layout (sibling, not nested)

```
astro-site/                           # NEW, isolated
├── src/
│   ├── pages/
│   │   ├── index.astro               # home
│   │   ├── about.astro
│   │   ├── philosophy/
│   │   │   ├── index.astro           # pillar index
│   │   │   └── [pillar].astro        # stoicism, marcus-aurelius, seneca…
│   │   ├── quotes/
│   │   │   └── [slug].astro          # one per xlsx row
│   │   ├── llms.txt.ts               # GEO manifest
│   │   ├── sitemap.xml.ts
│   │   ├── robots.txt.ts
│   │   └── rss.xml.ts
│   ├── content/config.ts             # Astro content collections
│   ├── components/
│   │   ├── SEOHead.astro
│   │   ├── QuoteCard.astro
│   │   ├── IGEmbed.astro
│   │   ├── LeadForm.astro
│   │   └── Schema.astro
│   └── lib/
│       ├── xlsx_loader.py            # openpyxl, called by Astro integration
│       ├── slug.ts                   # slug + collision handling
│       └── seo.ts                    # meta helpers
├── public/
│   ├── fonts/                        # self-hosted, CWV
│   ├── images/                       # OG default, logo, post stills
│   └── og/                           # per-quote OG cards
├── astro.config.mjs
├── package.json
└── README.md
```

### Out-of-band

```
scripts/audit_site.sh                 # starts astro dev → /seo audit → kills dev
docs/audits/<YYYY-MM-DD>/             # markdown + PDF outputs land here
```

### Coupling

- `quotes.xlsx` is the only shared artifact. Symlink from `astro-site/data/quotes.xlsx` → `../../quotes.xlsx`. Read-only at site root
- `public/images/post-stills/` may symlink to `output/` reel stills
- Zero coupling to `pipeline.py`, `studio/`, `remotion/`, `src/`, `data/pipeline.db`

### Env vars

| Var | Scope | Purpose |
|---|---|---|
| `PUBLIC_FORMSPREE_ID` | build (public) | Formspree form endpoint for email capture |
| `PUBLIC_IG_HANDLE` | build (public) | Instagram handle for CTAs + schema |
| `PUBLIC_SITE_URL` | build (public) | Canonical URL base (`http://localhost:4321` for dev) |

No secrets in repo. Verified by grep check in acceptance gate.

## Pages

### `index.astro` — home

Sections, top→bottom:
1. Hero: hero quote (one featured per build), brand statement, IG follow CTA (primary)
2. "What this is" 3-card strip: daily reel, philosophy library, AI-citable
3. Lead form (Formspree): email + name → weekly quote pack
4. Portfolio: 6 most-recent posted reels as IG embeds
5. Footer: schema `Organization` JSON-LD, social links, contact

Schema on this page: `WebSite`, `Organization`, `Person` (site author).

### `about.astro`

Origin story, author bio, philosophy credentials (E-E-A-T: Experience, Expertise, Authoritativeness, Trustworthiness). Schema: `AboutPage` + `Person`.

### `philosophy/index.astro` + `philosophy/[pillar].astro`

Index lists all pillars. Each pillar page has:
- Hand-written intro (~150 words)
- Auto-linked `QuoteCard` grid for every quote tagged with that pillar
- Internal links to other pillars

Pillars seeded from xlsx `pillar` column (distinct values). Schema: `CollectionPage` + `BreadcrumbList`.

### `quotes/[slug].astro` — auto-generated

One page per xlsx row. Slug = `{author-slug}-{first-4-words-slug}`. Per-page:
- Full quote text, attribution
- Pillar chips → pillar pages
- Related quotes (same author or pillar, exclude self)
- IG-share CTA + canonical link
- `Quotation` JSON-LD
- Per-quote OG card (`/og/{slug}.png`)

Filtering at build: skip rows with empty `quote_text` or `author`. Count skipped, log warning, don't fail build. Slug collisions → `-2`, `-3` suffix, log warning.

### `llms.txt`

Per [llms.txt spec](https://llmstxt.org/). Sections:
- `# Title` — site name + one-line description
- `# Description` — longer positioning
- `# Key pages` — bulleted links to home, about, each pillar, top 20 quotes
- `# Key quotes` — 20 best quotes with author + URL
- `# Contact` — IG handle, email (form)

### `sitemap.xml`, `robots.txt`, `rss.xml`

Standard. Sitemap includes all quote + pillar pages. RSS = latest 20 quotes.

## Components

| Component | Props | Behavior |
|---|---|---|
| `SEOHead.astro` | `meta: {title, description, ogImage, canonical?}` | Title, desc, canonical, OG, Twitter, hreflang=`en`, favicon |
| `QuoteCard.astro` | `quote: Quote` | Text, author, pillar chips, link to detail page |
| `IGEmbed.astro` | `permalink: string` | `<blockquote class="instagram-media">` + embed.js lazy-loaded; falls back to `<a>` if script fails |
| `LeadForm.astro` | — | Native `<form action="https://formspree.io/f/{ID}">`, no JS |
| `Schema.astro` | `type: string, props: object` | Renders `<script type="application/ld+json">` from props |

## Data flow at build

```
quotes.xlsx (read-only symlink)
        │
        ▼  [openpyxl in xlsx_loader.py, called by Astro integration hook]
quotes collection (in-memory, validated)
        │
        ├──> /quotes/[slug] pages    (~one per valid row)
        ├──> /philosophy/[pillar]    (grouped by pillar tag)
        ├──> /index featured quotes  (latest 6 by row order)
        ├──> /llms.txt key quotes    (top 20 by row order)
        └──> /rss.xml                (latest 20 by row order)
```

Lead capture flow (runtime):

```
visitor submits email
        │ browser POST, no JS framework
        ▼
https://formspree.io/f/{PUBLIC_FORMSPREE_ID}
        │
        ▼
Formspree → forwards to operator email + optional Google Sheet
```

No DB, no auth, no PII on our side.

## Error handling

### Build-time

- `xlsx_loader.py` wraps `openpyxl.load_workbook` in try/except → abort build with `file:line` error on hard failures (missing file, unreadable)
- Per-row: missing required field (`quote_text`, `author`, `pillar`) → skip with counted warning. Don't fail build (one bad row shouldn't block site)
- Slug collision → suffix `-2`, `-3`…, warning
- Missing OG image → fall back to `public/og/default.png`, warning
- Empty pillar set (no rows have pillars) → fail build with explicit error (philosophy index would be empty)

### Runtime (browser)

- Formspree unreachable → form shows "Try again later" + mailto fallback
- IG embed script fails to load → `IGEmbed` falls back to `<a>` permalink
- Image 404 → `onerror` swaps to alt text + placeholder

### Audit pass

- `scripts/audit_site.sh` retries astro dev startup 3× with 5s backoff
- Port 4321 already in use → kill stale dev server before starting new one
- `/seo audit` non-zero exit → re-run, not partial-commit; both markdown + PDF required
- Audit outputs land in `docs/audits/<YYYY-MM-DD>/` only if both files present

## Testing

### Unit (pytest)

| File | Tests | Coverage |
|---|---|---|
| `tests/test_xlsx_loader.py` | 6 | Valid file count, bad row skip+warn, missing file error, missing required field, empty pillar fail, malformed xlsx |
| `tests/test_slug.py` | 4 | Normal slug, unicode author→ASCII, empty quote→skipped, collision→suffixed |
| `tests/test_seo_head.ts` | 4 | Snapshot per page-type (home/quote/pillar/about): canonical, OG, hreflang |
| `tests/test_schema.ts` | 5 | JSON-LD shape per type (WebSite, Organization, Quotation, CollectionPage, BreadcrumbList) |

Schema-dts type-check on every JSON-LD payload at test time.

### End-to-end (CI / manual)

1. `npm run build` exits 0
2. `npm run preview` then `curl /, /about, /philosophy, /philosophy/stoicism, /quotes/<sample>, /llms.txt, /sitemap.xml, /rss.xml, /robots.txt` → all 200
3. `python scripts/audit_site.sh` → `/seo audit http://localhost:4321` completes
4. llms.txt parses per llmstxt.org spec
5. `grep -rE '(API_KEY|SECRET|TOKEN|PASSWORD)' astro-site/` → no matches (env-var only)
6. Schema.org validation via Schema Markup Validator (or `schema-dts` programmatic check) → no unknown @type

### Acceptance gate (defines "done")

1. All unit tests pass
2. Build succeeds; all expected routes return 200
3. `/seo audit` produces a markdown report with **≥ 1 actionable finding** in each of: technical SEO, schema, GEO. Empty audit = nothing to fix = useless audit
4. llms.txt parses per spec
5. No secrets in repo
6. A second audit pass after fixes shows measurable improvement (count of high-severity findings down, or net-new schema coverage)

Iterate on findings before declaring done.

## Things explicitly NOT done (defer or skip)

- Buying a domain — defer until content + audit signal is good
- Hosting — defer; site is local-only
- Multi-language — `en` only initially
- Analytics — defer until traffic exists
- Comments / on-site social — IG is the social surface
- Per-quote A/B testing
- Editorial workflow / draft mode for quotes
- Integration with `studio/` agents (sub-project 2 territory)

## Open questions for plan phase

- Exact Formspree vs alternatives (Buttondown, ConvertKit free tier) — picked Formspree for zero-config + free 50 submissions/mo
- IG handle — must be provided before first build (env var)
- Whether to symlink `quotes.xlsx` (recommended) or copy (simpler but stale-prone)
- Whether `astro dev` (port 4321) is conflict-free in this env

## References

- claude-seo README: https://github.com/AgricIDaniel/claude-seo
- llms.txt spec: https://llmstxt.org/
- Schema.org Quotation: https://schema.org/Quotation
- Astro content collections: https://docs.astro.build/en/guides/content-collections/
- Formspree: https://formspree.io