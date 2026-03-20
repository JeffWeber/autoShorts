# Architecture

**autonovel** is an autonomous pipeline that generates complete novels from a seed concept, and **short story collections** from pre-built divergent timeline bibles. Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch), it applies a modify → evaluate → keep/discard loop to fiction writing, producing print-ready PDFs.

Two modes of operation:
- **Novel mode** — generates a full novel (~80K words, 22-26 chapters) from a seed concept
- **Collection mode** — generates 6-10 standalone short stories (1500-3000 words each) set within a pre-built divergent timeline

First novel production: *The Second Son of the House of Bells* — 19 chapters, 79,456 words, 6 revision cycles.

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

### Collection Model

The collection pipeline receives a pre-built world (timeline bible) rather than generating one. Stories are standalone but share a timeline, requiring consistency without continuity.

```
Layer 5:  voice.md                ← HOW we write (calibrated from bible tone + user style)
Layer 4:  References/bible.md     ← WHAT EXISTS (pre-built divergent timeline — input, not generated)
Layer 3:  stories/*_characters.md ← WHO ACTS (1-3 per story, lighter than novel depth)
Layer 2:  collection_plan.md      ← WHICH WINDOWS to open (8 story briefs mined from timeline)
Layer 1:  stories/story_NN.md     ← THE ACTUAL PROSE
Cross-cutting: canon.md           ← WHAT IS TRUE (extracted from bible, 80-150 entries)
```

| Aspect | Novel Pipeline | Collection Pipeline |
|--------|---------------|-------------------|
| World | Generated (`gen_world.py`) | Pre-built (`References/bible.md`) |
| Structure | 22-26 sequential chapters | 6-10 standalone stories |
| Words/piece | 3000-3500 per chapter | 1500-3000 per story |
| Characters | Persistent cast, deep arcs | 1-3 per story, lighter sketches |
| Continuity | Prev/next chapter context | Shared timeline only |
| Revision | 3-6 cycles, multi-chapter cascading | 1 pass per story + 1 collection-level pass |

---

## Pipeline Phases

### Novel Mode

```
seed.txt ──► PHASE 1: FOUNDATION ──► PHASE 2: DRAFTING ──► PHASE 3: REVISION ──► PHASE 4: EXPORT
              (world, characters,      (sequential chapter    (adversarial edit,    (PDF)
               outline, voice,          drafting with          reader panel,
               canon, mystery)          eval gates)            Opus review loop)
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

### Novel Phase 4 — Export (~30 min)

| Output | Scripts |
|--------|---------|
| Arc summary | `build_arc_summary.py` |
| Outline rebuild | `build_outline.py` |
| PDF (trade paperback) | `typeset/build_tex.py` → `tectonic novel.tex` |

### Collection Mode

```
bible.md ──► PHASE 1: INTAKE ──► PHASE 2: PLAN ──► PHASE 3: DRAFTING ──► PHASE 4: POLISH+EXPORT
              (validate bible,     (mine moments,     (per-story:           (collection panel,
               extract canon,       select 8 stories,   draft, evaluate,      Opus review,
               calibrate voice)     generate briefs)    adversarial edit,     typeset)
                                                        revise if <6.5)
```

Orchestrated by `run_collection_pipeline.py`. State tracked in `state.json`.

#### Phase 1 — Intake (~15-30 min)

| Step | Script | Output | Gate |
|------|--------|--------|------|
| Validate bible | `validate_bible.py` | `eval_logs/bible_validation.json` | `bible_score > 6.0` |
| Extract canon | `gen_canon_from_bible.py` | `canon.md` | 50+ entries |
| Voice calibration | manual / `voice_fingerprint.py` | `voice.md` | — |

#### Phase 2 — Collection Plan (~30-60 min)

`gen_collection_plan.py` mines the bible in two phases:
1. **Mine** 15-20 candidate moments across eras
2. **Select** 8 that maximize coverage, variety, and tonal range

Each brief includes: era, year, location, POV character, dramatic question, opening/closing image, 3-5 beats, sensory anchors, required canon facts, emotional register, target word count, thematic connections.

Gate: `collection_plan_score > 7.0` (max 5 iterations).

#### Phase 3 — Drafting + Revision (~4-8 hours)

Per story:
1. `gen_story_characters.py N` → `stories/story_NN_characters.md`
2. `draft_story.py N` → `stories/story_NN.md` (Sonnet 4.6, T=0.8, 22 anti-pattern rules)
3. `evaluate.py --story=N` → keep if score > 6.5, else retry (max 3 attempts)
4. `adversarial_edit.py story N` → 5-10 cuts
5. `gen_brief.py --story-eval N` + `gen_revision.py story N brief.md` if score < 6.5

#### Phase 4 — Polish + Export (~1-2 hours)

1. `reader_panel.py --collection` → 3-persona anthology evaluation
2. `review.py --collection` → Opus dual-persona collection review
3. Targeted revision of weakest story
4. `evaluate.py --collection` → final collection score
5. `typeset/build_collection_tex.py` → LaTeX export

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

**Novel mode** scores: prose quality, voice adherence, character distinctiveness, beat coverage, theme coherence, pacing, dialogue, emotional authenticity, structural integrity.

**Story mode** scores 8 dimensions: voice adherence, experiential density, character specificity, prose quality, canon compliance, world integration, completeness, engagement.

**Collection mode** scores 7 dimensions: coverage, variety, coherence, world teaching, redundancy, ordering, overall quality.

### Reader Panel (`reader_panel.py`)

**Novel mode**: 4 personas (editor, genre reader, writer, first reader) each answer 10 questions. Consensus (3-4 agreement) becomes revision targets.

**Collection mode**: 3 personas (anthology editor, SF reader, general reader) answer 8 questions: weakest story, strongest story, missing perspective, redundant pair, ordering, world understanding, would recommend, haunts you.

---

## Script Inventory (27 Python files)

### Novel Foundation (7)
`seed.py` · `gen_world.py` · `gen_characters.py` · `gen_outline.py` · `gen_outline_part2.py` · `gen_canon.py` · `voice_fingerprint.py`

### Collection Intake & Planning (4) — *new*
`validate_bible.py` · `gen_canon_from_bible.py` · `gen_collection_plan.py` · `gen_story_characters.py`

### Drafting (3)
`draft_chapter.py` · `run_drafts.py` · `draft_story.py`

### Evaluation (5) — *evaluate.py, reader_panel.py, review.py support both modes*
`evaluate.py` · `adversarial_edit.py` · `compare_chapters.py` · `reader_panel.py` · `review.py`

### Revision (3) — *gen_brief.py, gen_revision.py support both modes*
`gen_brief.py` · `gen_revision.py` · `apply_cuts.py`

### Orchestration & Utilities (4)
`run_pipeline.py` (novel) · `run_collection_pipeline.py` (collection) · `build_arc_summary.py` · `build_outline.py`

### Typesetting (2)
`typeset/build_tex.py` (novel) · `typeset/build_collection_tex.py` (collection)

---

## External Integrations

| Service | Purpose | Models / Endpoints | Env Var |
|---------|---------|--------------------|---------|
| **Anthropic** | Writing, evaluation, review | Sonnet 4.6 (writer), Opus 4.6 (judge/review) | `ANTHROPIC_API_KEY` |

All API calls use `httpx` directly against REST endpoints. Anthropic calls include `anthropic-beta: context-1m-2025-08-07` for 1M context window.

---

## State & Logging

| File / Directory | Purpose |
|-----------------|---------|
| `state.json` | Pipeline progress: phase, iteration, scores, chapters/stories drafted, revision cycle |
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

---

## Directory Structure

```
autoShorts/
├── chapters/                  Novel chapters (ch_01.md … ch_NN.md)
├── stories/                   Collection stories (story_01.md … story_10.md)
│   └── story_NN_characters.md Per-story character sketches
├── References/
│   └── bible.md               Pre-built divergent timeline (collection input)
├── typeset/
│   ├── build_tex.py           Novel chapters → LaTeX converter
│   └── build_collection_tex.py Collection stories → LaTeX converter
│
├── [Novel foundation]         seed.py, gen_world.py, gen_characters.py,
│                              gen_outline.py, gen_outline_part2.py,
│                              gen_canon.py, voice_fingerprint.py
├── [Collection intake/plan]   validate_bible.py, gen_canon_from_bible.py,
│                              gen_collection_plan.py, gen_story_characters.py
├── [Drafting]                 draft_chapter.py, run_drafts.py, draft_story.py
├── [Evaluation]               evaluate.py, adversarial_edit.py,
│                              compare_chapters.py, reader_panel.py, review.py
├── [Revision]                 gen_brief.py, gen_revision.py, apply_cuts.py
├── [Orchestration]            run_pipeline.py (novel),
│                              run_collection_pipeline.py (collection),
│                              build_arc_summary.py, build_outline.py
│
├── [Foundation docs]          voice.md, world.md, characters.md,
│                              outline.md, canon.md, MYSTERY.md
├── [Collection docs]          collection_plan.md, canon.md (from bible)
├── [Framework docs]           README.md, PIPELINE.md, CRAFT.md,
│                              ANTI-SLOP.md, ANTI-PATTERNS.md,
│                              WORKFLOW.md, program.md
│
├── state.json                 Pipeline state tracker
├── results.tsv                Experiment log
├── eval_logs/                 Per-evaluation results
├── edit_logs/                 Adversarial cuts, panel results, review metadata
├── briefs/                    Revision briefs per chapter/story
├── pyproject.toml             Project config (uv)
├── .env.example               API key template
└── main.py                    Entry point
```
