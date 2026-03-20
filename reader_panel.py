#!/usr/bin/env python3
"""
4-reader panel for full-arc novel evaluation.
Each reader has a distinct persona and evaluates the NOVEL, not chapters.
The disagreements between readers are where editorial decisions live.

Usage: python reader_panel.py
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-opus-4-6")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_BASE = os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com")

READERS = {
    "editor": {
        "name": "The Editor",
        "system": (
            "You are a senior fiction editor at a major publishing house. "
            "You've edited 200+ novels. You care about prose texture, subtext, "
            "sentence-level craft, and whether the voice is consistent and earned. "
            "You notice when the narrator over-explains, when dialogue sounds "
            "written rather than spoken, when a metaphor is borrowed rather than "
            "earned. You are not cruel but you are precise. You've seen enough "
            "competent prose to know the difference between good and alive. "
            "You respond with valid JSON only."
        ),
    },
    "genre_reader": {
        "name": "The Genre Reader",
        "system": (
            "You are an avid fantasy reader who reads 50+ novels a year. "
            "You care about pacing, mystery, worldbuilding payoff, and whether "
            "you want to keep turning pages. You get bored by beautiful prose "
            "that doesn't GO anywhere. You notice when an investigation stalls, "
            "when tension plateaus, when the author is more in love with their "
            "world than their story. You compare everything to Sanderson, Le Guin, "
            "Jemisin, Rothfuss, Hobb. You are generous with what you love and "
            "blunt about what bores you. You respond with valid JSON only."
        ),
    },
    "writer": {
        "name": "The Writer",
        "system": (
            "You are a published fantasy author with 5 novels and a Hugo nomination. "
            "You read as a craftsperson. You notice structure: where the beats fall, "
            "whether foreshadowing pays off, whether character arcs complete. You "
            "notice when technique shows versus when it disappears into the story. "
            "The highest compliment you give is 'I forgot I was reading.' The worst "
            "thing you can say is 'I can see the outline.' You care about the gap "
            "between what a novel attempts and what it achieves. You respond with "
            "valid JSON only."
        ),
    },
    "first_reader": {
        "name": "The First Reader",
        "system": (
            "You are a thoughtful general reader. Not a writer, not an editor, "
            "not a genre expert. You read for the experience. You know what you "
            "feel but not always why. You notice when you're moved, when you're "
            "bored, when you're confused, when you want to tell someone about "
            "what you just read. You don't use craft terminology. You say things "
            "like 'I didn't care about this part' and 'I had to put the book down "
            "after this scene because I needed a minute.' Your feedback is emotional "
            "and honest, not analytical. You respond with valid JSON only."
        ),
    },
}

READER_PROMPT = """You have just read a complete fantasy novel in summary form.
The summaries include chapter-by-chapter events, opening and closing passages
from each chapter, and key dialogue. The full novel is 72,422 words across
24 chapters.

{arc_summary}

Now answer these questions about the NOVEL AS A WHOLE. Be specific.
Quote passages when you can. Name chapter numbers.

Respond with JSON:
{{
  "momentum_loss": "Where does the story lose momentum? Name the specific chapter(s) and what causes the drag. If it never loses momentum, say so and explain why.",
  
  "earned_ending": "Does the ending feel earned by everything before it? Does Cass's choice in Ch 22 land? Does the final image in Ch 24 mirror Ch 1 in a way that satisfies? What, if anything, feels unearned?",
  
  "cut_candidate": "If the novel had to be 10% shorter (~7,000 words), which chapter or section would you cut first? Why? What would be lost?",
  
  "missing_scene": "Is there a scene the novel NEEDS that it doesn't have? A conversation that should happen, a moment that's earned but never delivered, a character who deserves more page time? Be specific about where it would go.",
  
  "thinnest_character": "Which character feels thinnest by the end? Who do you want to know more about? Who could be cut without the novel suffering?",
  
  "best_scene": "What's the single best scene in the novel? Quote the moment that made you feel something. Why does it work?",
  
  "worst_scene": "What's the single weakest scene? What goes wrong? How would you fix it?",
  
  "would_recommend": "Would you recommend this novel? To whom? What would you say about it in one sentence?",
  
  "haunts_you": "Is there a line or moment that stays with you after reading? Quote it.",
  
  "next_book": "Would you read the author's next book? Why or why not?"
}}
"""

def call_reader(reader_key, arc_summary):
    import httpx
    reader = READERS[reader_key]
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": JUDGE_MODEL,
        "max_tokens": 4000,
        "temperature": 0.7,  # Higher temp for personality
        "system": reader["system"],
        "messages": [{"role": "user", "content": READER_PROMPT.format(arc_summary=arc_summary)}],
    }
    resp = httpx.post(f"{API_BASE}/v1/messages", headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"]
    
    # Parse JSON
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```\w*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
    start = raw.find('{')
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(raw)):
            c = raw[i]
            if escape: escape = False; continue
            if c == '\\' and in_string: escape = True; continue
            if c == '"' and not escape: in_string = not in_string; continue
            if in_string: continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(raw[start:i+1], strict=False)
    return json.loads(raw, strict=False)

def find_disagreements(results):
    """Find where readers disagree -- that's where the editorial decisions live."""
    disagreements = []
    
    for question in ["momentum_loss", "cut_candidate", "thinnest_character", "worst_scene"]:
        answers = {k: v.get(question, "") for k, v in results.items()}
        # Extract chapter numbers mentioned
        chapters_mentioned = {}
        for reader, answer in answers.items():
            chs = set(re.findall(r'Ch(?:apter)?\s*(\d+)', answer, re.IGNORECASE))
            chapters_mentioned[reader] = chs
        
        # Find chapters where only some readers flagged an issue
        all_chs = set()
        for chs in chapters_mentioned.values():
            all_chs.update(chs)
        
        for ch in all_chs:
            flagged_by = [r for r, chs in chapters_mentioned.items() if ch in chs]
            not_flagged = [r for r, chs in chapters_mentioned.items() if ch not in chs]
            if flagged_by and not_flagged:
                disagreements.append({
                    "question": question,
                    "chapter": int(ch),
                    "flagged_by": flagged_by,
                    "not_flagged": not_flagged,
                    "details": {r: answers[r][:200] for r in flagged_by}
                })
    
    return disagreements

# ---------------------------------------------------------------------------
# Collection mode: 3-reader panel for short story collections
# ---------------------------------------------------------------------------

COLLECTION_READERS = {
    "editor": {
        "name": "The Editor",
        "system": (
            "You are a senior fiction editor specializing in literary speculative fiction "
            "anthologies. You've edited award-winning collections. You care about prose "
            "texture, voice consistency across stories, and whether each story earns its "
            "place in the collection. You notice when a story is doing exposition instead "
            "of dramatizing. You respond with valid JSON only."
        ),
    },
    "genre_reader": {
        "name": "The SF Reader",
        "system": (
            "You are a devoted reader of speculative fiction who reads 40+ books a year "
            "and subscribes to every major SF magazine. You care about worldbuilding "
            "payoff, plausibility, and whether the speculative element does WORK in each "
            "story. You get bored by stories that use their world as wallpaper. You compare "
            "to Ted Chiang, Kim Stanley Robinson, Ursula Le Guin, Ken Liu. You respond "
            "with valid JSON only."
        ),
    },
    "general_reader": {
        "name": "The General Reader",
        "system": (
            "You are a thoughtful reader who picks up anthologies at bookstores. You read "
            "for the experience. You notice when you're moved, bored, confused, or wanting "
            "to tell someone about what you read. You don't use craft terminology. You say "
            "things like 'this one stayed with me' and 'I skimmed the middle of this one.' "
            "Your feedback is emotional and honest. You respond with valid JSON only."
        ),
    },
}

COLLECTION_READER_PROMPT = """You have just read a short story collection set in a
divergent timeline. The collection contains {story_count} stories. Here are summaries
of each story (opening and closing passages):

{story_summaries}

Now answer these questions about the COLLECTION AS A WHOLE. Be specific.
Reference stories by number.

Respond with JSON:
{{
  "weakest_story": "Which story is the weakest? Why? What would you cut or replace it with?",

  "strongest_story": "Which story is the strongest? What makes it work? Quote a moment if you can.",

  "missing_perspective": "Is there a voice, era, or experience underrepresented in this collection? What story is MISSING?",

  "redundant_pair": "Do any two stories feel like they're telling the same story or covering the same ground? Which ones?",

  "ordering": "Does the reading order work? Would you move any stories? Why?",

  "world_understanding": "After reading all stories, how well do you understand this timeline? What aspects feel vivid? What feels abstract?",

  "would_recommend": "Would you recommend this collection? To whom? What would you say about it?",

  "haunts_you": "Which moment from any story stays with you? Quote it if you can."
}}
"""


def call_collection_reader(reader_key, story_summaries, story_count):
    import httpx
    reader = COLLECTION_READERS[reader_key]
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    prompt = COLLECTION_READER_PROMPT.format(
        story_summaries=story_summaries,
        story_count=story_count,
    )
    payload = {
        "model": JUDGE_MODEL,
        "max_tokens": 4000,
        "temperature": 0.7,
        "system": reader["system"],
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(f"{API_BASE}/v1/messages", headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"]

    # Parse JSON (same as call_reader)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```\w*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
    start = raw.find('{')
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(raw)):
            c = raw[i]
            if escape: escape = False; continue
            if c == '\\' and in_string: escape = True; continue
            if c == '"' and not escape: in_string = not in_string; continue
            if in_string: continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(raw[start:i+1], strict=False)
    return json.loads(raw, strict=False)


def run_collection_panel():
    """Run the 3-reader panel on a short story collection."""
    stories_dir = BASE_DIR / "stories"
    story_files = sorted(f for f in stories_dir.glob("story_*.md")
                         if "_characters" not in f.name)

    if not story_files:
        print("ERROR: No stories found in stories/", file=sys.stderr)
        sys.exit(1)

    # Build summaries
    summaries = []
    for st_file in story_files:
        text = st_file.read_text()
        num_match = re.search(r'story_(\d+)', st_file.name)
        num = int(num_match.group(1)) if num_match else 0
        wc = len(text.split())
        head = text[:600]
        tail = text[-600:] if len(text) > 600 else ""
        summaries.append(
            f"Story {num} ({wc} words):\n"
            f"  Opening: {head}...\n"
            f"  Closing: ...{tail}\n"
        )

    story_summaries = "\n".join(summaries)
    story_count = len(story_files)

    results = {}
    for reader_key, reader_info in COLLECTION_READERS.items():
        print(f"\n{'='*50}")
        print(f"READING: {reader_info['name']}")
        print(f"{'='*50}")

        try:
            result = call_collection_reader(reader_key, story_summaries, story_count)
            results[reader_key] = result
            print(f"  Weakest: {result.get('weakest_story', '')[:150]}...")
            print(f"  Strongest: {result.get('strongest_story', '')[:150]}...")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Print results
    print(f"\n{'='*60}")
    print("COLLECTION PANEL RESULTS")
    print(f"{'='*60}")

    for question in ["weakest_story", "strongest_story", "missing_perspective",
                      "redundant_pair", "ordering", "world_understanding",
                      "would_recommend", "haunts_you"]:
        print(f"\n--- {question.upper()} ---")
        for reader_key in COLLECTION_READERS:
            if reader_key in results:
                answer = results[reader_key].get(question, "N/A")
                print(f"  [{COLLECTION_READERS[reader_key]['name']}]: {answer[:300]}")

    # Save
    output = {
        "mode": "collection",
        "readers": results,
        "story_count": story_count,
        "timestamp": datetime.now().isoformat(),
    }
    logs_dir = BASE_DIR / "edit_logs"
    logs_dir.mkdir(exist_ok=True)
    out_path = logs_dir / "collection_panel.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    import argparse as _argparse
    parser = _argparse.ArgumentParser(description="Reader panel evaluation")
    parser.add_argument("--collection", action="store_true",
                        help="Run collection panel (3 readers, story-level)")
    args = parser.parse_args()

    if args.collection:
        run_collection_panel()
        return

    # Original novel mode
    arc_summary = (BASE_DIR / "arc_summary.md").read_text()

    results = {}
    for reader_key, reader_info in READERS.items():
        print(f"\n{'='*50}")
        print(f"READING: {reader_info['name']}")
        print(f"{'='*50}")

        try:
            result = call_reader(reader_key, arc_summary)
            results[reader_key] = result
            print(f"  Momentum loss: {result.get('momentum_loss', '')[:150]}...")
            print(f"  Best scene: {result.get('best_scene', '')[:150]}...")
            print(f"  Would recommend: {result.get('would_recommend', '')[:150]}...")
        except Exception as e:
            print(f"  ERROR: {e}")

    disagreements = find_disagreements(results)

    print(f"\n{'='*60}")
    print("READER PANEL RESULTS")
    print(f"{'='*60}")

    for question in ["momentum_loss", "earned_ending", "cut_candidate", "missing_scene",
                      "thinnest_character", "best_scene", "worst_scene", "would_recommend",
                      "haunts_you", "next_book"]:
        print(f"\n--- {question.upper()} ---")
        for reader_key in READERS:
            if reader_key in results:
                answer = results[reader_key].get(question, "N/A")
                print(f"  [{READERS[reader_key]['name']}]: {answer[:300]}")

    if disagreements:
        print(f"\n{'='*60}")
        print("DISAGREEMENTS (editorial decisions needed)")
        print(f"{'='*60}")
        for d in disagreements:
            print(f"\n  {d['question']} -- Ch {d['chapter']}")
            print(f"    Flagged by: {', '.join(d['flagged_by'])}")
            print(f"    Not flagged: {', '.join(d['not_flagged'])}")

    output = {
        "readers": results,
        "disagreements": disagreements,
        "timestamp": datetime.now().isoformat()
    }
    out_path = BASE_DIR / "edit_logs" / "reader_panel.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
