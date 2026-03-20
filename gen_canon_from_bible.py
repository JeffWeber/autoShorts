#!/usr/bin/env python3
"""
Extract hard facts from a divergent timeline bible into canon.md.

Usage: python gen_canon_from_bible.py [path/to/bible.md]
       Default: References/bible.md

Output: canon.md (structured fact database for continuity checking)
"""
import sys
from pathlib import Path
from api_client import call_llm

BASE_DIR = Path(__file__).parent

SYSTEM_PROMPT = (
    "You are a continuity editor extracting hard facts from a speculative fiction "
    "timeline bible. You are precise, exhaustive, and never invent facts "
    "that aren't in the source material. Every entry must be traceable to a "
    "specific statement in the source document."
)


def main():
    bible_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "References" / "bible.md"
    if not bible_path.exists():
        print(f"ERROR: Bible not found at {bible_path}", file=sys.stderr)
        sys.exit(1)

    bible = bible_path.read_text()
    word_count = len(bible.split())
    print(f"Bible: {bible_path} ({word_count} words)", file=sys.stderr)

    prompt = f"""Extract EVERY hard fact from this divergent timeline bible into a structured
canon database. A "hard fact" is anything a story writer must not contradict: dates, numbers,
percentages, names, locations, rules, established events, technology specs, social structures,
economic facts, and sensory baselines.

THE TIMELINE BIBLE:
{bible}

FORMAT THE OUTPUT AS CANON.MD with these categories:

## Timeline & Dates
- Specific years, durations, sequences of events
- Era boundaries and transition dates

## Geography & Locations
- Named places, distances, physical properties
- Regional differences, climate zones affected

## Technology & Infrastructure
- Specific technologies, their capabilities, their limitations
- Energy numbers, efficiency stats, capacity figures

## Economic Facts
- Costs, prices, ratios, trade relationships
- Resource scarcity, production figures

## Social Structure
- Population numbers, demographic splits
- Class divisions, governance structures
- Named organizations, treaties, accords

## Scientific & Biological
- Specific biological mechanisms, species data
- Health statistics, medical facts
- Environmental measurements

## Cultural & Daily Life
- Food, customs, norms, taboos
- Cultural practices, art forms, social rituals
- Sensory baselines (what things sound/smell/look like)

## Named Entities
- Specific technologies, programs, treaties, locations by proper name
- Vocabulary/lexicon terms with their definitions

## Rules & Constraints
- Physical laws of this timeline
- What is possible and what is not
- System limitations, failure modes

RULES:
- One fact per bullet point. Short. Specific. Checkable.
- Include the source section in parentheses after each fact (e.g., "Divergence Era", "Present Era").
- Aim for 80-150 entries. Be exhaustive.
- Quantify wherever the source provides numbers.
- If the bible gives a range (e.g., "seventy to eighty percent"), record the range exactly.
- DO NOT invent facts. Only record what's explicitly stated.
- DO NOT editorialize or add interpretation.
"""

    print("Extracting canon facts...", file=sys.stderr)
    result = call_llm("writer", prompt, system=SYSTEM_PROMPT, temperature=0.2, max_tokens=16000, timeout=300)

    # Count entries
    entry_count = result.count("\n- ")
    print(f"Extracted ~{entry_count} canon entries", file=sys.stderr)

    # Save
    out_path = BASE_DIR / "canon.md"
    out_path.write_text(result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(result)


if __name__ == "__main__":
    main()
