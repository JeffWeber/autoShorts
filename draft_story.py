#!/usr/bin/env python3
"""
Draft a single short story using the writer model.

Usage: python draft_story.py <story_num>
       Reads the story brief from collection_plan.md, characters, bible, voice, canon.

Output: stories/story_NN.md
"""
import re
import sys
from pathlib import Path
from api_client import call_llm

BASE_DIR = Path(__file__).parent
STORIES_DIR = BASE_DIR / "stories"

SYSTEM_PROMPT = (
    "You are a literary speculative fiction writer drafting a standalone short story "
    "set in a pre-built divergent timeline. You write fiction that makes the reader "
    "EXPERIENCE what it's like to live in this world — through one person's eyes, "
    "in one specific moment. You are not writing a summary of events or an essay "
    "about the world. You are writing a STORY with a character who wants something, "
    "encounters resistance, and is changed. "
    "You follow the voice definition exactly. You hit every beat in the brief. "
    "You never use words from the banned list. You show, never tell emotions. "
    "Your prose is specific, sensory, grounded. You trust the reader. "
    "You write the FULL story — do not truncate, summarize, or skip ahead."
)


def load_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def extract_story_brief(plan_text, story_num):
    """Extract a specific story's brief from the collection plan."""
    pattern = rf'####\s*Story\s*{story_num}\b.*?(?=####\s*Story\s*{story_num + 1}\b|$)'
    match = re.search(pattern, plan_text, re.DOTALL)
    return match.group(0).strip() if match else ""


def extract_bible_section_for_era(bible_text, era_hint):
    """Extract the relevant era section from the bible."""
    if not era_hint:
        return bible_text[:4000]

    for pattern in [
        rf'##.*?{re.escape(era_hint)}.*?(?=\n## |\Z)',
        rf'(?:Era|Epoch|Period).*?{re.escape(era_hint)}.*?(?=\n## |\Z)',
    ]:
        match = re.search(pattern, bible_text, re.DOTALL | re.I)
        if match:
            return match.group(0)

    return bible_text[:4000]


def main():
    story_num = int(sys.argv[1])

    # Load context
    plan = load_file(BASE_DIR / "collection_plan.md")
    if not plan:
        print("ERROR: collection_plan.md not found", file=sys.stderr)
        sys.exit(1)

    bible = load_file(BASE_DIR / "References" / "bible.md")
    voice = load_file(BASE_DIR / "voice.md")
    canon = load_file(BASE_DIR / "canon.md")

    # Story-specific context
    story_brief = extract_story_brief(plan, story_num)
    if not story_brief:
        print(f"ERROR: Story {story_num} not found in collection_plan.md", file=sys.stderr)
        sys.exit(1)

    characters = load_file(STORIES_DIR / f"story_{story_num:02d}_characters.md")

    # Extract era for targeted bible context
    era_match = re.search(r'\*\*Era:\*\*\s*(.+)', story_brief)
    era_hint = era_match.group(1).strip() if era_match else ""
    bible_section = extract_bible_section_for_era(bible, era_hint)

    # Also get the "present era" / sensory / lexicon sections which are always useful
    sensory_section = ""
    for label in ["Sensory Profile", "Lexicon", "Present Era"]:
        match = re.search(rf'##\s*{label}.*?(?=\n## |\Z)', bible, re.DOTALL)
        if match:
            sensory_section += match.group(0) + "\n\n"

    # Extract target word count from brief
    wc_match = re.search(r'\*\*Target word count:\*\*\s*(\d+)', story_brief)
    target_words = int(wc_match.group(1)) if wc_match else 2000

    prompt = f"""Write a complete short story for a collection set in a divergent timeline.

THIS STORY'S BRIEF (hit every beat):
{story_brief}

CHARACTER SKETCHES:
{characters if characters else "(No character file — create characters from the brief)"}

TIMELINE BIBLE (relevant era):
{bible_section}

{f"SENSORY & CULTURAL REFERENCE:{chr(10)}{sensory_section}" if sensory_section else ""}

{f"CANON FACTS (do not contradict these):{chr(10)}{canon}" if canon else ""}

{f"VOICE DEFINITION (follow this exactly):{chr(10)}{voice}" if voice else ""}

WRITING INSTRUCTIONS:
1. Write the COMPLETE story. Target ~{target_words} words. Do not truncate or summarize.
2. Start IN THE WORLD. The first paragraph should put the reader in a specific place
   with a specific person doing something specific. No preamble, no context-setting
   narration, no "In the year 20XX..."
3. The timeline does WORK in this story. The world isn't backdrop — it shapes every
   choice, every meal, every sensory detail. If you could transplant this story to
   present-day Earth, you've failed.
4. Hit ALL beats from the brief in order.
5. Weave in the required canon facts NATURALLY — through action, dialogue, or
   sensory detail, never through exposition dumps.
6. Show sensory detail from the bible: what the character sees, hears, smells, feels.
7. End on an IMAGE, not a summary. The closing should resonate, not explain.
8. No banned words from the voice definition.
9. No AI fiction tells: no "a sense of," no "couldn't help but feel," no "eyes widened."
10. Vary sentence length. Short sentences for impact. Longer ones for perception.
11. Trust the reader. Don't explain what scenes mean. Let them land.

PATTERNS TO AVOID:
12. NO triadic sensory lists. Never "X. Y. Z." as three separate items in a row.
13. NO "She/He did not [verb]" more than once per story.
14. NO "She/He thought about [X]" constructions. Replace with: the thought itself
    as a fragment, a physical action, or dialogue.
15. NO over-explaining after showing. If a scene demonstrates something, do not
    have the narrator restate it.
16. NO section breaks unless absolutely necessary for a time jump. Max 1 per story.
17. VARY paragraph length deliberately. Include at least one 1-2 sentence paragraph
    and one 5+ sentence paragraph.
18. At least one moment that surprises — a character saying the wrong thing, an
    emotional beat arriving early or late, a detail that breaks the expected pattern.
19. 70%+ in-scene (dialogue and action, not summary).
20. Dialogue should sound like speech, not prose. Characters should occasionally
    stumble, trail off, or say something slightly wrong.
21. NO opening with weather, waking up, or looking in a mirror.
22. The story must have a TURN — a moment where something shifts for the character.
    Not necessarily a plot twist, but a change in understanding, feeling, or resolve.

Write the story now. Full text, beginning to end.
"""

    print(f"Drafting Story {story_num}...", file=sys.stderr)
    result = call_llm("writer", prompt, system=SYSTEM_PROMPT, temperature=0.8, max_tokens=16000, timeout=600)

    STORIES_DIR.mkdir(exist_ok=True)
    out_path = STORIES_DIR / f"story_{story_num:02d}.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)
    print(result)


if __name__ == "__main__":
    main()
