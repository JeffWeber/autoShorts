#!/usr/bin/env python3
"""
Validate a divergent timeline bible for completeness and richness.

Usage: python validate_bible.py [path/to/bible.md]
       Default: References/bible.md

Checks for required sections (eras, rules, sensory details, lexicon),
then asks an LLM to assess richness and identify gaps.

Output: bible_score (0-10) to stdout + eval_logs/<timestamp>_bible.json
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-opus-4-6")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_BASE = os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com")
EVAL_LOG_DIR = BASE_DIR / "eval_logs"
EVAL_LOG_DIR.mkdir(exist_ok=True)


def call_judge(prompt, max_tokens=4000):
    import httpx
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": JUDGE_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "system": (
            "You are a speculative fiction editor evaluating worldbuilding documents. "
            "You assess whether a timeline bible contains enough material to support "
            "a collection of 6-10 short stories set in that world. "
            "Always respond with valid JSON. No markdown fences, no preamble."
        ),
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(f"{API_BASE}/v1/messages", headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def parse_json_response(text):
    """Extract JSON from response that might have markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1], strict=False)
    return json.loads(text, strict=False)


# --- Structural checks (no LLM) ---

def structural_check(text):
    """Check for required sections in the bible. Returns (pass_count, total, details)."""
    checks = {
        "has_eras": bool(re.search(r'(?:era|epoch|period|phase)\b', text, re.I)),
        "has_timeline_dates": bool(re.search(r'\b\d{4}\b', text)),
        "has_rules": bool(re.search(r'(?:rules?|constraints?|the rules)\b', text, re.I)),
        "has_sensory_details": bool(re.search(
            r'(?:smell|sound|acoustic|optical|visual|tactile|taste|atmospheric)',
            text, re.I
        )),
        "has_daily_life": bool(re.search(
            r'(?:day in the life|daily|morning|breakfast|commute|routine)',
            text, re.I
        )),
        "has_social_structure": bool(re.search(
            r'(?:class|stratif|social|economic|governance|political)',
            text, re.I
        )),
        "has_lexicon_or_terms": bool(re.search(
            r'(?:lexicon|glossary|terminology|term|vocab)',
            text, re.I
        )),
        "has_key_events": bool(re.search(
            r'(?:key (?:historic )?events?|timeline|milestone)',
            text, re.I
        )),
    }
    passed = sum(1 for v in checks.values() if v)
    return passed, len(checks), checks


# --- LLM evaluation ---

BIBLE_EVAL_PROMPT = """Evaluate this divergent timeline bible for its ability to support
a collection of 6-10 standalone short stories (1500-3000 words each).

THE BIBLE:
{bible_text}

WORD COUNT: {word_count}

Score these dimensions (0-10):

- era_coverage: Does the bible define distinct eras/epochs with clear transitions?
  Stories will be set across different eras. Are there enough distinct periods?

- sensory_richness: Does the bible describe how this world FEELS? Sounds, smells,
  textures, visual landscape, daily experiences? A story writer needs sensory
  anchors, not just facts.

- human_scale: Does the bible contain enough about ordinary human life (daily
  routines, food, work, relationships, emotions) to ground a character-level story?
  Grand geopolitics is not enough.

- internal_logic: Are the rules of this divergent world consistent and specific
  enough that a story writer won't accidentally contradict them?

- story_potential: How many distinct, compelling short story premises could you
  generate from this bible? Rate the density of dramatizable moments.

- lexicon_depth: Does the bible introduce world-specific vocabulary, concepts,
  or social categories that would make stories feel grounded in THIS timeline?

- tension_map: Are there clear tensions, conflicts, or dilemmas at the personal
  and societal level? Stories need conflict. How many distinct conflict types
  does this bible support?

Respond with JSON:
{{
  "era_coverage": {{"score": N, "note": "...", "gap": "biggest weakness"}},
  "sensory_richness": {{"score": N, "note": "...", "gap": "..."}},
  "human_scale": {{"score": N, "note": "...", "gap": "..."}},
  "internal_logic": {{"score": N, "note": "...", "gap": "..."}},
  "story_potential": {{"score": N, "note": "...", "gap": "..."}},
  "lexicon_depth": {{"score": N, "note": "...", "gap": "..."}},
  "tension_map": {{"score": N, "note": "...", "gap": "..."}},
  "estimated_story_count": N,
  "suggested_story_moments": ["3-5 specific moments that would make great stories"],
  "critical_gaps": ["things missing that a story writer would need"],
  "bible_score": N,
  "verdict": "one-sentence assessment"
}}

A bible scoring 6+ is usable. A bible scoring 8+ is rich enough to support
excellent fiction. Be honest about gaps.
"""


def evaluate_bible(bible_text):
    word_count = len(bible_text.split())
    prompt = BIBLE_EVAL_PROMPT.format(bible_text=bible_text, word_count=word_count)
    raw = call_judge(prompt)
    return parse_json_response(raw)


def main():
    bible_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "References" / "bible.md"
    if not bible_path.exists():
        print(f"ERROR: Bible not found at {bible_path}", file=sys.stderr)
        sys.exit(1)

    bible_text = bible_path.read_text()
    word_count = len(bible_text.split())

    print(f"Bible: {bible_path} ({word_count} words)", file=sys.stderr)

    # Structural checks
    passed, total, checks = structural_check(bible_text)
    print(f"Structural checks: {passed}/{total}", file=sys.stderr)
    for name, ok in checks.items():
        status = "PASS" if ok else "MISS"
        print(f"  [{status}] {name}", file=sys.stderr)

    if passed < 4:
        print(f"\nWARNING: Only {passed}/{total} structural checks passed. "
              "Bible may be too thin for story generation.", file=sys.stderr)

    # LLM evaluation
    print("\nRunning LLM evaluation...", file=sys.stderr)
    result = evaluate_bible(bible_text)
    result["structural_checks"] = checks
    result["structural_pass_rate"] = f"{passed}/{total}"
    result["word_count"] = word_count
    result["bible_path"] = str(bible_path)

    # Output score
    score = result.get("bible_score", 0)
    print("---")
    print(f"bible_score: {score}")
    print(f"word_count: {word_count}")
    print(f"structural: {passed}/{total}")
    print(f"verdict: {result.get('verdict', '')}")

    for dim in ["era_coverage", "sensory_richness", "human_scale", "internal_logic",
                "story_potential", "lexicon_depth", "tension_map"]:
        d = result.get(dim, {})
        print(f"{dim}: {d.get('score', '?')} -- {d.get('note', '')}")

    gaps = result.get("critical_gaps", [])
    if gaps:
        print(f"critical_gaps: {gaps}")

    moments = result.get("suggested_story_moments", [])
    if moments:
        print(f"suggested_moments: {moments}")

    # Save log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = EVAL_LOG_DIR / f"{timestamp}_bible.json"
    with open(log_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\neval_log: {log_path}")


if __name__ == "__main__":
    main()
