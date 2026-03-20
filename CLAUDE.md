# CLAUDE.md

See @ARCHITECTURE.md for full pipeline design (novel mode + collection mode).

## Project Overview

Autonomous fiction generation pipeline with two modes:
- **Novel mode**: `python run_pipeline.py` — full novel from seed concept
- **Collection mode**: `python run_collection_pipeline.py --bible References/bible.md` — short story collection from a divergent timeline bible

## Build & Run

```bash
# Install dependencies
uv sync

# Collection pipeline (primary active mode)
python run_collection_pipeline.py --bible References/bible.md
python run_collection_pipeline.py --phase intake    # just validate + extract canon
python run_collection_pipeline.py --phase plan      # just generate collection plan

# Individual scripts
python validate_bible.py References/bible.md
python gen_canon_from_bible.py References/bible.md
python gen_collection_plan.py
python draft_story.py 1
python evaluate.py --story=1
python adversarial_edit.py story 1
python review.py --collection
python reader_panel.py --collection
```

## Code Conventions

- All API calls use `httpx` directly against Anthropic REST endpoints (no SDK wrapper)
- Writer model: Sonnet 4.6 (T=0.8) — creative generation
- Judge model: Opus 4.6 (T=0.3) — evaluation and review (different model prevents self-congratulation)
- Config via `.env` + `python-dotenv`: `ANTHROPIC_API_KEY`, `AUTONOVEL_WRITER_MODEL`, `AUTONOVEL_JUDGE_MODEL`, `AUTONOVEL_API_BASE_URL`
- Include `anthropic-beta: context-1m-2025-08-07` header for long-context calls
- State tracked in `state.json`, experiment log in `results.tsv`

## Key Directories

- `stories/` — drafted short stories + per-story character files
- `chapters/` — novel chapters (novel mode only)
- `References/` — timeline bibles (input for collection mode)
- `eval_logs/` — evaluation results (mechanical + LLM scores)
- `edit_logs/` — adversarial cuts, panel results, review metadata
- `briefs/` — auto-generated revision instructions

## Important Patterns

- Scripts that support both modes use subcommands: `adversarial_edit.py story <N>`, `gen_revision.py story <N> <brief>`
- Evaluation dimensions differ by mode — check `evaluate.py` for STORY_PROMPT vs CHAPTER_PROMPT vs COLLECTION_PROMPT
- Canon compliance is critical — stories must not contradict facts in `canon.md`
- The dual immune system: mechanical slop detection (regex, no LLM) runs first, then LLM judge scores dimensions
