#!/usr/bin/env python3
"""
Generate character sketches for a single story from its brief + bible.

Usage: python gen_story_characters.py <story_num>
       Reads the story brief from collection_plan.md and the bible.

Output: stories/story_NN_characters.md
"""
import re
import sys
from pathlib import Path
from api_client import call_llm

BASE_DIR = Path(__file__).parent
STORIES_DIR = BASE_DIR / "stories"

SYSTEM_PROMPT = (
    "You are creating character sketches for a short story set in a speculative "
    "fiction timeline. Characters must feel specific and human — not archetypes. "
    "Keep sketches tight: these are for 1500-3000 word stories, not novels. "
    "Focus on what makes each character DISTINCT in speech, physicality, and desire."
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
    """Try to extract the relevant era section from the bible."""
    if not era_hint:
        return bible_text[:3000]  # fallback: first 3000 chars

    # Try to find a section matching the era
    for pattern in [
        rf'##.*?{re.escape(era_hint)}.*?(?=\n## |\Z)',
        rf'(?:Era|Epoch|Period).*?{re.escape(era_hint)}.*?(?=\n## |\Z)',
    ]:
        match = re.search(pattern, bible_text, re.DOTALL | re.I)
        if match:
            return match.group(0)

    return bible_text[:4000]  # fallback


def main():
    story_num = int(sys.argv[1])

    plan = load_file(BASE_DIR / "collection_plan.md")
    if not plan:
        print("ERROR: collection_plan.md not found", file=sys.stderr)
        sys.exit(1)

    bible = load_file(BASE_DIR / "References" / "bible.md")
    voice = load_file(BASE_DIR / "voice.md")
    canon = load_file(BASE_DIR / "canon.md")

    story_brief = extract_story_brief(plan, story_num)
    if not story_brief:
        print(f"ERROR: Story {story_num} not found in collection_plan.md", file=sys.stderr)
        sys.exit(1)

    # Try to extract era from brief for targeted bible context
    era_match = re.search(r'\*\*Era:\*\*\s*(.+)', story_brief)
    era_hint = era_match.group(1).strip() if era_match else ""
    bible_section = extract_bible_section_for_era(bible, era_hint)

    prompt = f"""Create character sketches for this short story.

STORY BRIEF:
{story_brief}

TIMELINE CONTEXT (relevant era):
{bible_section}

{f"CANON FACTS:{chr(10)}{canon[:2000]}" if canon else ""}

{f"VOICE GUIDELINES:{chr(10)}{voice[:1500]}" if voice else ""}

Create 1-3 characters for this story. For each character:

## [Character Name]
- **Age:** [specific]
- **Role:** [their job/position in this world]
- **Physical signature:** One distinctive physical detail that reveals something
  about their life (not eye color — something earned: calluses, posture, a scar,
  how they hold their hands)
- **Desire:** What they want RIGHT NOW, in this story (one sentence)
- **Fear:** What they're afraid of (one sentence)
- **Speech pattern:** How they talk — sentence length, vocabulary, verbal tics,
  what they avoid saying. Give 2-3 example lines of dialogue.
- **Relationship to the timeline:** How has this world specifically shaped this
  person? What would be different about them if the divergence hadn't happened?
- **The thing they don't say:** What are they holding back in this story?

RULES:
- These are short story characters, not novel characters. Keep sketches to
  ~200-300 words per character.
- Make them specific to THIS timeline. A drone technician in 2045 is not the
  same as a generic mechanic.
- Speech patterns must be distinct enough to identify without dialogue tags.
- The POV character gets the most detail. Supporting characters get less.
- Names should feel natural for the era, location, and culture described in
  the bible.
"""

    print(f"Generating characters for Story {story_num}...", file=sys.stderr)
    result = call_llm("writer", prompt, system=SYSTEM_PROMPT, temperature=0.7, max_tokens=4000, timeout=180)

    STORIES_DIR.mkdir(exist_ok=True)
    out_path = STORIES_DIR / f"story_{story_num:02d}_characters.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(result)


if __name__ == "__main__":
    main()
