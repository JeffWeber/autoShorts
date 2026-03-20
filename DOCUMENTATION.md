# Documentation

## Model & Provider Configuration

All LLM calls in the pipeline go through `api_client.py`, which supports two providers: **Anthropic** (direct) and **OpenRouter** (access to any model).

### Quick Setup

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### Using Anthropic (Default)

```env
AUTONOVEL_API_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here

AUTONOVEL_WRITER_MODEL=claude-sonnet-4-6
AUTONOVEL_JUDGE_MODEL=claude-opus-4-6
AUTONOVEL_REVIEW_MODEL=claude-opus-4-6
```

This is the default configuration. The writer model handles all creative generation (drafting stories, characters, outlines), while the judge and review models handle evaluation and literary analysis. Using a different model for judging than for writing prevents self-congratulation.

### Using OpenRouter

[OpenRouter](https://openrouter.ai) gives you access to models from multiple providers (Anthropic, Google, Meta, etc.) through a single API key.

```env
AUTONOVEL_API_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-your-key-here

AUTONOVEL_WRITER_MODEL=anthropic/claude-sonnet-4-6
AUTONOVEL_JUDGE_MODEL=google/gemini-2.5-pro
AUTONOVEL_REVIEW_MODEL=anthropic/claude-opus-4-6
```

**Important:** OpenRouter model IDs use a `provider/model` format (e.g., `anthropic/claude-sonnet-4-6`). Check [openrouter.ai/models](https://openrouter.ai/models) for available model IDs.

You can also override the OpenRouter base URL if needed:

```env
OPENROUTER_BASE_URL=https://openrouter.ai
```

### The Three Model Roles

| Role | Env Var | Used For | Default Temperature |
|------|---------|----------|-------------------|
| **Writer** | `AUTONOVEL_WRITER_MODEL` | Drafting stories, characters, outlines, canon extraction, revisions | 0.2-1.0 (varies by task) |
| **Judge** | `AUTONOVEL_JUDGE_MODEL` | Evaluation scoring, adversarial editing, reader panel, bible validation | 0.2-0.3 |
| **Review** | `AUTONOVEL_REVIEW_MODEL` | Deep literary manuscript review (review.py only) | 0.3 |

The writer model should be fast and creative. The judge and review models should be strong at critical analysis. Using a different model (or at least a different role) for judging vs writing is intentional — it prevents the system from rating its own output favorably.

### Mixing Models

You can use different providers' models for different roles. For example, with OpenRouter you could use Claude for writing and Gemini for judging:

```env
AUTONOVEL_API_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-your-key-here

AUTONOVEL_WRITER_MODEL=anthropic/claude-sonnet-4-6
AUTONOVEL_JUDGE_MODEL=google/gemini-2.5-pro
AUTONOVEL_REVIEW_MODEL=anthropic/claude-opus-4-6
```

### All Configuration Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTONOVEL_API_PROVIDER` | No | `anthropic` | `anthropic` or `openrouter` |
| `ANTHROPIC_API_KEY` | If provider=anthropic | — | Your Anthropic API key |
| `OPENROUTER_API_KEY` | If provider=openrouter | — | Your OpenRouter API key |
| `AUTONOVEL_WRITER_MODEL` | No | `claude-sonnet-4-6` | Model for creative generation |
| `AUTONOVEL_JUDGE_MODEL` | No | `claude-opus-4-6` | Model for evaluation |
| `AUTONOVEL_REVIEW_MODEL` | No | `claude-opus-4-6` | Model for literary review |
| `AUTONOVEL_API_BASE_URL` | No | `https://api.anthropic.com` | Anthropic API base URL |
| `OPENROUTER_BASE_URL` | No | `https://openrouter.ai` | OpenRouter API base URL |

---

## Starting a New Story Collection

A collection generates 6-10 standalone short stories set within a shared divergent timeline. Here's the high-level process:

### 1. Write a Timeline Bible

Create a markdown file (e.g., `References/bible.md`) describing your divergent timeline. This is the creative input — everything else is generated from it. The bible should include:

- The point of divergence (what changed from real history)
- Key historical events and their dates
- How society, technology, culture, and politics evolved differently
- Geographic and institutional details
- Enough texture across multiple eras for stories to be set in different time periods

### 2. Configure Your Models

Edit `.env` to set your preferred provider and models (see above).

### 3. Run the Pipeline

**Full automated run:**
```bash
python run_collection_pipeline.py --bible References/bible.md --from-scratch
```

**Or run phases individually:**

```bash
# Phase 1: Intake — validate bible, extract canon facts, calibrate voice
python run_collection_pipeline.py --phase intake --bible References/bible.md

# Phase 2: Plan — mine the timeline for story moments, select 8 stories
python run_collection_pipeline.py --phase plan

# Phase 3: Drafting — write each story, evaluate, revise if needed
python run_collection_pipeline.py --phase drafting

# Phase 4: Polish — collection-level review, targeted revision, typeset
python run_collection_pipeline.py --phase polish
```

### 4. What Each Phase Produces

| Phase | What Happens | Key Outputs |
|-------|-------------|-------------|
| **Intake** | Validates your bible scores 6.0+, extracts 50+ canon facts, sets voice | `canon.md`, `voice.md`, `eval_logs/bible_validation.json` |
| **Plan** | Mines 15-20 candidate moments, selects 8 with best coverage/variety | `collection_plan.md` (8 story briefs with beats, characters, tone) |
| **Drafting** | Per story: generate characters, draft, evaluate (>6.5), adversarial edit, revise | `stories/story_01.md` through `story_08.md`, character files, eval logs |
| **Polish** | Reader panel, Opus review, revise weakest story, final collection score | `edit_logs/` review files, final `eval_logs/` scores |

### 5. Starting Over

To start a completely fresh collection (clears all generated content):

```bash
python run_collection_pipeline.py --bible References/bible.md --from-scratch
```

Or manually: delete `state.json`, `stories/`, `canon.md`, `collection_plan.md`, `eval_logs/`, `edit_logs/`, and `briefs/`.

### 6. Checking Progress

Pipeline state is tracked in `state.json`. You can inspect it to see which phase you're in, how many stories are drafted, current scores, etc.

The experiment log `results.tsv` records every keep/discard decision with scores and word counts.
