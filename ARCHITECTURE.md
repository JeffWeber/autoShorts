# Architecture

**autonovel** is an autonomous pipeline that generates complete novels from a seed concept. Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch), it applies a modify → evaluate → keep/discard loop to fiction writing, producing print-ready PDFs, ePubs, audiobooks, and landing pages.

First production: *The Second Son of the House of Bells* — 19 chapters, 79,456 words, 6 revision cycles.

---

## Coevolutionary Model

The novel is built from five interdependent layers plus a cross-cutting facts database. Changes propagate both downward (lore change → outline change → chapter revision) and upward (writing reveals gaps → update lore → check downstream).

```
Layer 5:  voice.md        ← HOW we write (prose patterns, vocabulary wells, anti-exemplars)
Layer 4:  world.md        ← WHAT EXISTS (magic system, geography, factions, history)
Layer 3:  characters.md   ← WHO ACTS (wound/want/need/lie, speech patterns, 3 sliders)
Layer 2:  outline.md      ← WHAT HAPPENS (chapter beats, foreshadowing ledger)
Layer 1:  chapters/*.md   ← THE ACTUAL PROSE
Cross-cutting: canon.md   ← WHAT IS TRUE (hard facts, cross-referenced, 400+ entries)
```

Supporting documents: `MYSTERY.md` (central secret, author-only), `program.md` (agent instructions per phase).

---

## Pipeline Phases

```
seed.txt ──► PHASE 1: FOUNDATION ──► PHASE 2: DRAFTING ──► PHASE 3: REVISION ──► PHASE 4: EXPORT
              (world, characters,      (sequential chapter    (adversarial edit,    (PDF, ePub,
               outline, voice,          drafting with          reader panel,         audiobook,
               canon, mystery)          eval gates)            Opus review loop)     cover art)
```

Orchestrated by `run_pipeline.py` (892 lines). State tracked in `state.json`.

### Phase 1 — Foundation (~2-4 hours)

Loops until `foundation_score > 7.5 AND lore_score > 7.0`:

| Step | Script | Output |
|------|--------|--------|
| World bible | `gen_world.py` | `world.md` |
| Character registry | `gen_characters.py` | `characters.md` |
| Chapter outline | `gen_outline.py` | `outline.md` (part 1) |
| Foreshadowing ledger | `gen_outline_part2.py` | `outline.md` (part 2) |
| Voice discovery | `voice_fingerprint.py` | `voice.md` (part 2) |
| Canon facts | `gen_canon.py` | `canon.md` |
| Evaluate | `evaluate.py --phase=foundation` | score → keep/discard |

### Phase 2 — Drafting (~8-16 hours)

For each chapter sequentially:

1. `draft_chapter.py N` — writes `chapters/ch_NN.md` (~3,000-3,500 words)
   - Model: Sonnet 4.6, temperature 0.8
   - Context: voice + world + characters + outline entry + prev/next chapter tails
   - 24 anti-pattern rules in system prompt
2. `evaluate.py --chapter=N` — keep if score > 6.0, else retry (max 5 attempts)
3. Extract new canon entries → append to `canon.md`

Batch mode: `run_drafts.py`

### Phase 3 — Revision (~4-8 hours, 3-6 cycles)

**Structural revision (cycles 1-3):**

1. `adversarial_edit.py all` → cut candidates per chapter (OVER-EXPLAIN ~32%, REDUNDANT ~26%, FAT, TELL, etc.)
2. `apply_cuts.py` → apply mechanical cuts
3. `reader_panel.py` → 4-persona evaluation (editor, genre reader, writer, first reader)
4. `gen_brief.py --panel N` → auto-generate revision brief from consensus items
5. `gen_revision.py N brief.md` → rewrite chapter from brief
6. `evaluate.py --full` → full novel score

**Opus review loop (cycles 4+):**

1. `review.py` → full manuscript to Opus (dual-persona: literary critic + professor of fiction)
2. Stopping: stars ≥ 4.5 with no major items, or plateau (Δ < 0.3 over 2 cycles)
3. `gen_brief.py --auto` → brief from weakest chapter + review feedback
4. `gen_revision.py` → rewrite, then `apply_cuts.py` → cleanup

Supporting tools: `compare_chapters.py` (Elo tournament ranking)

### Phase 4 — Export (~30 min)

| Output | Scripts |
|--------|---------|
| Arc summary | `build_arc_summary.py` |
| Outline rebuild | `build_outline.py` |
| PDF (trade paperback) | `typeset/build_tex.py` → `tectonic novel.tex` |
| ePub | `typeset/epub_metadata.yaml` + `epub_style.css` |
| Cover art | `gen_art.py` → `gen_cover_composite.py` → `gen_cover_print.py` |
| Art directions | `gen_art_directions.py` |
| Audiobook | `gen_audiobook_script.py` → `gen_audiobook.py` |
| Landing page | `landing/index.html` |

---

## Quality Assurance — Dual Immune System

### Mechanical Slop Detection (regex, no LLM)

Built into `evaluate.py`:

- **Tier 1 Banned** (~15 words): delve, utilize, leverage, facilitate, tapestry, paradigm, synergy, …
- **Tier 2 Suspicious** (~25 words): robust, comprehensive, seamless, pivotal, intricate, profound, …
- **Tier 3 Filler Phrases**: "it's worth noting that", "let's dive into", …
- **Fiction AI Tells**: "a sense of", "couldn't help but feel", "eyes widened", "air was thick with", …
- **Show-Don't-Tell**: detects emotional telling ("felt angry", "seemed sad", …)
- **Metrics**: em-dash density, sentence length CV, transition opener ratio

### LLM Judge (Opus, T=0.3)

Scores across dimensions: prose quality, voice adherence, character distinctiveness, beat coverage, theme coherence, pacing, dialogue, emotional authenticity, structural integrity.

### Reader Panel (`reader_panel.py`)

4 personas each answer 10 questions (momentum loss, earned ending, cut candidates, missing scenes, thinnest character, best/worst scene, would recommend, haunts you, next book). Consensus (3-4 agreement) becomes revision targets.

---

## Script Inventory (27 Python files)

### Foundation (7)
`seed.py` · `gen_world.py` · `gen_characters.py` · `gen_outline.py` · `gen_outline_part2.py` · `gen_canon.py` · `voice_fingerprint.py`

### Drafting (2)
`draft_chapter.py` · `run_drafts.py`

### Evaluation (5)
`evaluate.py` · `adversarial_edit.py` · `compare_chapters.py` · `reader_panel.py` · `review.py`

### Revision (3)
`gen_brief.py` · `gen_revision.py` · `apply_cuts.py`

### Art & Cover (4)
`gen_art.py` · `gen_art_directions.py` · `gen_cover_composite.py` · `gen_cover_print.py`

### Audiobook (2)
`gen_audiobook_script.py` · `gen_audiobook.py`

### Orchestration & Utilities (3)
`run_pipeline.py` · `build_arc_summary.py` · `build_outline.py`

### Typesetting (1)
`typeset/build_tex.py`

---

## External Integrations

| Service | Purpose | Models / Endpoints | Env Var |
|---------|---------|--------------------|---------|
| **Anthropic** | Writing, evaluation, review | Sonnet 4.6 (writer), Opus 4.6 (judge/review) | `ANTHROPIC_API_KEY` |
| **fal.ai** | Cover art, ornaments | Nano Banana 2 | `FAL_KEY` |
| **ElevenLabs** | Multi-voice audiobook | 13 character voices + narrator | `ELEVENLABS_API_KEY` |

All API calls use `httpx` directly against REST endpoints. Anthropic calls include `anthropic-beta: context-1m-2025-08-07` for 1M context window.

---

## State & Logging

| File / Directory | Purpose |
|-----------------|---------|
| `state.json` | Pipeline progress: phase, iteration, scores, chapters drafted, revision cycle, debts |
| `results.tsv` | Experiment log — every keep/discard decision with commit, score, word count |
| `eval_logs/*.json` | Per-evaluation results (mechanical + LLM scores, dimension breakdown) |
| `edit_logs/*.json` | Adversarial cuts, reader panel responses, Elo tournament results, review metadata |
| `briefs/*.md` | Auto-generated revision instructions per chapter per cycle |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Package manager | uv |
| HTTP client | httpx ≥ 0.28.1 |
| Config | python-dotenv ≥ 1.2.2 |
| Typesetting | LaTeX (XeTeX / Tectonic), EB Garamond |
| Web | Static HTML (landing page) |

---

## Directory Structure

```
autoShorts/
├── chapters/                  Novel chapters (ch_01.md … ch_NN.md)
├── landing/
│   └── index.html             Responsive landing page
├── typeset/
│   ├── build_tex.py           Chapters → LaTeX converter
│   ├── novel.tex              LaTeX template (5.5×8.5 trade paperback)
│   ├── epub_metadata.yaml     ePub metadata
│   ├── epub_style.css         ePub styling
│   └── epub_*.md              Front matter, back cover, colophon
│
├── [Foundation scripts]       seed.py, gen_world.py, gen_characters.py,
│                              gen_outline.py, gen_outline_part2.py,
│                              gen_canon.py, voice_fingerprint.py
├── [Drafting scripts]         draft_chapter.py, run_drafts.py
├── [Evaluation scripts]       evaluate.py, adversarial_edit.py,
│                              compare_chapters.py, reader_panel.py, review.py
├── [Revision scripts]         gen_brief.py, gen_revision.py, apply_cuts.py
├── [Art scripts]              gen_art.py, gen_art_directions.py,
│                              gen_cover_composite.py, gen_cover_print.py
├── [Audiobook scripts]        gen_audiobook_script.py, gen_audiobook.py
├── [Orchestration]            run_pipeline.py, build_arc_summary.py, build_outline.py
│
├── [Foundation docs]          voice.md, world.md, characters.md,
│                              outline.md, canon.md, MYSTERY.md
├── [Framework docs]           README.md, PIPELINE.md, CRAFT.md,
│                              ANTI-SLOP.md, ANTI-PATTERNS.md,
│                              WORKFLOW.md, program.md
│
├── state.json                 Pipeline state tracker
├── audiobook_voices.json      Character → voice mapping
├── results.tsv                Experiment log
├── pyproject.toml             Project config (uv)
├── .env.example               API key template
└── main.py                    Entry point
```
