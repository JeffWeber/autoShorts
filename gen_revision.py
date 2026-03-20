#!/usr/bin/env python3
"""
Revision chapter generator. Rewrites a chapter from a specific revision brief.
Usage: python gen_revision.py <chapter_num> <brief_file>
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

def call_writer(prompt, max_tokens=16000):
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
        "temperature": 0.8,
        "system": (
            "You are rewriting a fantasy novel chapter based on a specific revision brief. "
            "You follow the brief exactly. You preserve the voice, world, and characters "
            "from the existing draft while making the structural changes specified. "
            "You write the FULL chapter. Do not truncate or summarize."
        ),
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


def revise_chapter(ch_num, brief_file):
    """Revise a novel chapter (original mode)."""
    voice = (BASE_DIR / "voice.md").read_text()
    characters = (BASE_DIR / "characters.md").read_text()
    world = (BASE_DIR / "world.md").read_text()
    brief = Path(brief_file).read_text()

    prev_path = BASE_DIR / "chapters" / f"ch_{ch_num - 1:02d}.md"
    next_path = BASE_DIR / "chapters" / f"ch_{ch_num + 1:02d}.md"
    prev_tail = prev_path.read_text()[-2000:] if prev_path.exists() else "(first chapter)"
    next_head = next_path.read_text()[:1500] if next_path.exists() else "(last chapter)"

    old_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    old_text = old_path.read_text() if old_path.exists() else "(no existing draft)"

    prompt = f"""Rewrite Chapter {ch_num} of "The Second Son of the House of Bells."

REVISION BRIEF (follow this exactly):
{brief}

VOICE DEFINITION:
{voice}

CHARACTER REGISTRY:
{characters}

WORLD BIBLE:
{world}

PREVIOUS CHAPTER ENDING (maintain continuity):
{prev_tail}

NEXT CHAPTER OPENING (end so this flows into it):
{next_head}

THE EXISTING DRAFT (use as raw material -- keep what works, cut what doesn't):
{old_text}

ANTI-PATTERN RULES:
- NO triadic sensory lists (X. Y. Z.)
- NO "He did not [verb]" more than once
- NO "He thought about [X]" constructions
- NO "the way [X] did [Y]" more than twice
- NO "not X, but Y" formula in narration
- NO over-explaining after showing
- MAX 2 section breaks
- At least one moment that genuinely surprises
- 70%+ in-scene (dialogue and action, not summary)
- Dialogue should sound like speech, not prose

Write the FULL revised chapter now."""

    print(f"Rewriting Chapter {ch_num}...", file=sys.stderr)
    result = call_writer(prompt)

    out_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)


def revise_story(story_num, brief_file):
    """Revise a short story (collection mode)."""
    voice = load_file(BASE_DIR / "voice.md")
    bible = load_file(BASE_DIR / "References" / "bible.md")
    canon = load_file(BASE_DIR / "canon.md")
    characters = load_file(BASE_DIR / "stories" / f"story_{story_num:02d}_characters.md")
    brief = Path(brief_file).read_text()

    old_path = BASE_DIR / "stories" / f"story_{story_num:02d}.md"
    old_text = old_path.read_text() if old_path.exists() else "(no existing draft)"

    prompt = f"""Rewrite this short story set in a divergent timeline.

REVISION BRIEF (follow this exactly):
{brief}

VOICE DEFINITION:
{voice}

CHARACTER SKETCHES:
{characters if characters else "(use characters from existing draft)"}

TIMELINE BIBLE (reference):
{bible[:4000] if bible else "(no bible)"}

CANON FACTS (do not contradict):
{canon if canon else "(no canon)"}

THE EXISTING DRAFT (use as raw material -- keep what works, cut what doesn't):
{old_text}

ANTI-PATTERN RULES:
- NO triadic sensory lists (X. Y. Z.)
- NO "She/He did not [verb]" more than once
- NO "She/He thought about [X]" constructions
- NO "the way [X] did [Y]" more than twice
- NO "not X, but Y" formula in narration
- NO over-explaining after showing
- MAX 1 section break
- At least one moment that genuinely surprises
- 70%+ in-scene (dialogue and action, not summary)
- Dialogue should sound like speech, not prose
- End on an IMAGE, not a summary

Write the FULL revised story now."""

    print(f"Rewriting Story {story_num}...", file=sys.stderr)
    result = call_writer(prompt)

    out_path = BASE_DIR / "stories" / f"story_{story_num:02d}.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)


def main():
    # Story mode: gen_revision.py story <num> <brief_file>
    if len(sys.argv) >= 4 and sys.argv[1] == "story":
        story_num = int(sys.argv[2])
        brief_file = sys.argv[3]
        revise_story(story_num, brief_file)
    elif len(sys.argv) >= 3:
        ch_num = int(sys.argv[1])
        brief_file = sys.argv[2]
        revise_chapter(ch_num, brief_file)
    else:
        print("Usage: python gen_revision.py <chapter_num> <brief_file>")
        print("       python gen_revision.py story <story_num> <brief_file>")
        sys.exit(1)

if __name__ == "__main__":
    main()
