# WORKFLOW

Step-by-step guide to running autonovel.

For the full technical pipeline specification, see [PIPELINE.md](PIPELINE.md).

---

## Quick Start

```bash
# 1. Setup
cd ~/autonovel
cp .env.example .env   # Add your Anthropic API key

# 2. Generate a seed concept (or write your own in seed.txt)
uv run python seed.py

# 3. Create a branch for your novel
git checkout -b autonovel/my-novel

# 4. Run the full pipeline
uv run python run_pipeline.py --from-scratch
```

The pipeline will:
1. Build the world, characters, outline, and voice (Phase 1)
2. Draft all chapters sequentially (Phase 2)
3. Revise through automated cycles + Opus review (Phase 3)
4. Export to manuscript and PDF (Phase 4)

---

## Running Phases Individually

```bash
# Foundation only
uv run python run_pipeline.py --phase foundation

# Drafting only
uv run python run_pipeline.py --phase drafting

# Revision only (with max cycle limit)
uv run python run_pipeline.py --phase revision --max-cycles 5

# Export only
uv run python run_pipeline.py --phase export
```

---

## Manual Tools

### Evaluation
```bash
uv run python evaluate.py --phase=foundation   # Score planning docs
uv run python evaluate.py --chapter=5           # Score a chapter
uv run python evaluate.py --full                # Score the whole novel
```

### Revision
```bash
uv run python adversarial_edit.py all           # Find cuts in all chapters
uv run python apply_cuts.py all --types OVER-EXPLAIN REDUNDANT
uv run python reader_panel.py                   # 4-persona evaluation
uv run python review.py                         # Opus dual-persona review
uv run python gen_brief.py --auto               # Auto-generate revision brief
uv run python gen_revision.py 5 briefs/ch05.md  # Rewrite chapter from brief
```

### Export
```bash
uv run python build_outline.py                  # Rebuild outline
uv run python build_arc_summary.py              # Rebuild summaries
python3 typeset/build_tex.py && cd typeset && tectonic novel.tex  # PDF
```

---

## The Three Loops

```
INNER LOOP (agent, runs overnight):
  modify → evaluate → keep/discard → repeat

OUTER LOOP (you, when you check in):
  read results → steer program.md / evaluate.py / layer files
  → let the agent run again

REVIEW LOOP (after automated revision):
  send to Opus → parse review → fix top items → repeat
  → stop when no major unqualified items remain
```

You're not writing the novel. You're programming the system that
writes the novel.
