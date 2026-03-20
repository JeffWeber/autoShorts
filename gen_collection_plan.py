#!/usr/bin/env python3
"""
Generate a collection plan: mine a timeline bible for the best 6-10 short story
moments, then produce detailed briefs for each.

Usage: python gen_collection_plan.py [path/to/bible.md]
       Default: References/bible.md

Output: collection_plan.md
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_BASE = os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com")


def call_writer(prompt, system, max_tokens=16000, temperature=0.7):
    import httpx
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "context-1m-2025-08-07",
        "content-type": "application/json",
    }
    payload = {
        "model": WRITER_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(f"{API_BASE}/v1/messages", headers=headers, json=payload, timeout=600)
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def load_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def main():
    bible_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "References" / "bible.md"
    if not bible_path.exists():
        print(f"ERROR: Bible not found at {bible_path}", file=sys.stderr)
        sys.exit(1)

    bible = bible_path.read_text()
    voice = load_file(BASE_DIR / "voice.md")
    canon = load_file(BASE_DIR / "canon.md")

    # Read the bible's title/name
    first_line = bible.split('\n')[0].strip('#').strip()
    timeline_name = first_line if first_line else "Untitled Timeline"

    system_prompt = (
        "You are a literary speculative fiction editor planning a short story collection. "
        "You think like an anthology editor: each story must stand alone, but together they "
        "should teach the reader what it FEELS like to live in this timeline. You favor "
        "human-scale stories over geopolitical summaries. You look for moments of daily life, "
        "moral dilemmas, sensory experiences, and quiet revelations. You write in clean, "
        "direct prose. No AI slop words."
    )

    prompt = f"""Plan a collection of 6-10 short stories set in this divergent timeline.

TIMELINE BIBLE:
{bible}

{f"CANON (hard facts — stories must not contradict these):{chr(10)}{canon}" if canon else ""}

{f"VOICE GUIDELINES:{chr(10)}{voice}" if voice else ""}

YOUR TASK — TWO PHASES:

## Phase 1: Moment Mining

Read the entire bible. Identify 15-20 candidate MOMENTS — specific scenes, events,
daily-life snapshots, or human experiences that would make compelling short stories.

For each candidate, note:
- Era and approximate year
- Location
- POV character archetype (e.g., "a drone technician", "a mother on the Supplement Tier",
  "a Restorationist biologist")
- The dramatic question (what's at stake for THIS person?)
- Sensory hook (what does the reader see/hear/smell/taste/feel?)
- Why this moment matters to the timeline's larger story

PRIORITIZE moments that are:
- Experiential (the reader LIVES a day, an hour, a crisis — not a history lesson)
- Human-scale (one person's choice, dilemma, or realization)
- Sensory-rich (the bible provides enough detail to ground the scene)
- Varied (different eras, different social positions, different emotional registers)

AVOID:
- Moments that would read like a Wikipedia summary with characters pasted on
- Stories about world leaders making grand decisions (unless seen through a personal lens)
- Moments where the "character" is really just a camera for exposition

## Phase 2: Selection and Collection Design

From your 15-20 candidates, select 8 stories that together form a collection.

Selection criteria:
- **Era coverage**: At least one story from the early crisis, the middle rebuilding,
  and the present era
- **Social variety**: Stories from both the privileged and the marginalized, from
  different roles and ages
- **Tonal range**: Some stories should be intimate and quiet, others urgent, at least
  one should be uncomfortable or morally ambiguous
- **Experiential density**: Each story should make the reader FEEL something specific
  about this timeline that no other story in the collection does
- **Thematic resonance**: The stories should, read together, build toward the timeline's
  central unanswered question
- **No redundancy**: No two stories should dramatize the same type of moment or use
  the same character archetype

## Output Format

### Collection Overview
- Collection title
- Timeline name: {timeline_name}
- Number of stories: [6-10]
- Central question the collection explores
- Reading order rationale (why this sequence?)

### Thematic Echo Map
Which stories rhyme with each other? Note 3-5 thematic connections across stories
(e.g., "Story 2 and Story 7 both show someone choosing between safety and meaning,
but from opposite sides of the privilege divide").

### Story Briefs

For EACH selected story:

#### Story N: [Working Title]
- **Era:** [which era/epoch]
- **Year:** [approximate]
- **Location:** [specific place]
- **POV character:** [name, age, role — enough to draft from, but leave room for
  the drafting prompt to flesh out]
- **Dramatic question:** [what's at stake for this person?]
- **Opening image:** [the first thing the reader sees/hears/feels]
- **Closing image:** [the last thing — how does this story end emotionally?]
- **Beats:** 3-5 specific scene beats
  1. [beat]
  2. [beat]
  3. [beat]
- **Sensory anchors:** 2-3 specific sensory details from the bible that MUST appear
- **Required canon facts:** 3-5 specific facts from the bible that must be woven in
  naturally (not as exposition dumps)
- **What this story teaches the reader:** [what aspect of the timeline does this
  story make real?]
- **Emotional register:** [quiet/urgent/melancholy/defiant/etc.]
- **Target word count:** [1500-3000]
- **Connections to other stories:** [which other stories does this echo or contrast?]
"""

    print("Mining timeline for story moments...", file=sys.stderr)
    result = call_writer(prompt, system_prompt)

    # Save
    out_path = BASE_DIR / "collection_plan.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)

    # Count stories
    story_count = len([l for l in result.split('\n') if l.strip().startswith('#### Story')])
    print(f"Stories planned: {story_count}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)
    print(result)


if __name__ == "__main__":
    main()
