#!/usr/bin/env python3
"""
run_collection_pipeline.py — Automated short story collection pipeline.

Generates a collection of 6-10 short stories set in a divergent timeline bible.

Usage:
  python run_collection_pipeline.py                        # run from current state
  python run_collection_pipeline.py --from-scratch         # start fresh
  python run_collection_pipeline.py --phase intake         # run only intake
  python run_collection_pipeline.py --phase plan           # run only planning
  python run_collection_pipeline.py --phase drafting       # run only drafting
  python run_collection_pipeline.py --phase polish         # run only polish
  python run_collection_pipeline.py --bible path/to/bible  # specify bible path
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "state.json"
RESULTS_FILE = BASE_DIR / "results.tsv"
STORIES_DIR = BASE_DIR / "stories"
BRIEFS_DIR = BASE_DIR / "briefs"
EDIT_LOGS_DIR = BASE_DIR / "edit_logs"
EVAL_LOGS_DIR = BASE_DIR / "eval_logs"

BIBLE_THRESHOLD = 6.0
PLAN_THRESHOLD = 7.0
STORY_THRESHOLD = 6.5
MAX_PLAN_ITERS = 5
MAX_STORY_ATTEMPTS = 3

PHASE_ORDER = ["intake", "plan", "drafting", "polish"]


# ---------------------------------------------------------------------------
# Helpers: state management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return default_state()


def default_state() -> dict:
    return {
        "phase": "intake",
        "bible_path": "References/bible.md",
        "bible_score": 0.0,
        "voice_locked": False,
        "canon_entries": 0,
        "collection_plan_score": 0.0,
        "plan_iteration": 0,
        "stories_total": 0,
        "stories_drafted": 0,
        "stories_revised": 0,
        "collection_score": 0.0,
        "revision_cycle": 0,
    }


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Helpers: logging
# ---------------------------------------------------------------------------

def log_result(commit: str, phase: str, score, word_count: int,
               status: str, description: str):
    header = "commit\tphase\tscore\tword_count\tstatus\tdescription\n"
    if not RESULTS_FILE.exists() or RESULTS_FILE.stat().st_size == 0:
        RESULTS_FILE.write_text(header)
    with open(RESULTS_FILE, "a") as f:
        f.write(f"{commit}\t{phase}\t{score}\t{word_count}\t{status}\t{description}\n")


def banner(text: str, char: str = "=", width: int = 60):
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


def step(text: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {text}")


# ---------------------------------------------------------------------------
# Helpers: subprocess execution
# ---------------------------------------------------------------------------

def run_tool(cmd: str, timeout: int = 600, check: bool = False) -> subprocess.CompletedProcess:
    step(f"RUN: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(BASE_DIR),
        )
        if result.returncode != 0:
            print(f"    WARN: exit code {result.returncode}")
            stderr_preview = (result.stderr or "")[:300]
            if stderr_preview:
                print(f"    stderr: {stderr_preview}")
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr)
        return result
    except subprocess.TimeoutExpired:
        print(f"    ERROR: timed out after {timeout}s")
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="TIMEOUT")


def uv_run(script: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return run_tool(f"uv run python {script}", timeout=timeout)


# ---------------------------------------------------------------------------
# Helpers: git operations
# ---------------------------------------------------------------------------

def git_add_commit(message: str) -> str:
    run_tool("git add -A")
    result = run_tool(f'git commit -m "{message}" --allow-empty')
    if result.returncode == 0:
        hash_result = run_tool("git rev-parse --short HEAD")
        commit_hash = hash_result.stdout.strip()
        step(f"GIT COMMIT: {commit_hash} — {message}")
        return commit_hash
    else:
        step("GIT: nothing to commit or commit failed")
        return ""


def git_reset_hard(ref: str = "HEAD~1"):
    step(f"GIT RESET: {ref}")
    run_tool(f"git reset --hard {ref}")


# ---------------------------------------------------------------------------
# Helpers: score parsing
# ---------------------------------------------------------------------------

def parse_score(stdout: str, key: str = "overall_score") -> float:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith(f"{key}:"):
            val = line.split(":", 1)[1].strip()
            try:
                return float(val)
            except ValueError:
                continue
    return -1.0


def count_story_files() -> int:
    if not STORIES_DIR.exists():
        return 0
    return len([f for f in STORIES_DIR.glob("story_*.md")
                if "_characters" not in f.name])


def count_words_in_stories() -> int:
    total = 0
    if STORIES_DIR.exists():
        for f in STORIES_DIR.glob("story_*.md"):
            if "_characters" not in f.name:
                total += len(f.read_text().split())
    return total


def get_total_stories(state: dict) -> int:
    if state.get("stories_total", 0) > 0:
        return state["stories_total"]
    plan = BASE_DIR / "collection_plan.md"
    if plan.exists():
        text = plan.read_text()
        matches = re.findall(r'####\s*Story\s*(\d+)', text)
        if matches:
            return max(int(m) for m in matches)
    return 8  # default


# ---------------------------------------------------------------------------
# PHASE 1 — INTAKE
# ---------------------------------------------------------------------------

def run_intake(state: dict) -> dict:
    banner("PHASE 1: INTAKE", "=")

    bible_path = state.get("bible_path", "References/bible.md")

    # 1. Validate bible
    step("Validating timeline bible...")
    val_result = uv_run(f"validate_bible.py {bible_path}", timeout=300)
    bible_score = parse_score(val_result.stdout, "bible_score")
    step(f"Bible score: {bible_score}")

    if bible_score < BIBLE_THRESHOLD:
        step(f"WARNING: Bible score {bible_score} < {BIBLE_THRESHOLD}. "
             "Bible may be too thin for story generation.")
    state["bible_score"] = bible_score

    # 2. Extract canon
    step("Extracting canon facts from bible...")
    uv_run(f"gen_canon_from_bible.py {bible_path}", timeout=300)

    canon_path = BASE_DIR / "canon.md"
    if canon_path.exists():
        canon_text = canon_path.read_text()
        entry_count = canon_text.count("\n- ")
        state["canon_entries"] = entry_count
        step(f"Canon: {entry_count} entries extracted")
    else:
        step("WARNING: canon.md not created")
        state["canon_entries"] = 0

    # 3. Voice calibration
    # Check if voice.md already exists (user may have provided one)
    voice_path = BASE_DIR / "voice.md"
    if voice_path.exists() and len(voice_path.read_text().strip()) > 100:
        step("Voice file found — using existing voice.md")
        state["voice_locked"] = True
    else:
        step("No voice.md found — voice will need to be created")
        step("(For now, stories will draft without voice constraints)")
        state["voice_locked"] = False

    # Commit intake results
    commit_hash = git_add_commit(
        f"intake: bible_score {bible_score}, {state['canon_entries']} canon entries")
    log_result(commit_hash, "intake", bible_score, 0, "keep",
               f"Bible validated, canon extracted")

    state["phase"] = "plan"
    save_state(state)

    banner(f"INTAKE COMPLETE — bible_score {bible_score}, "
           f"{state['canon_entries']} canon entries")
    return state


# ---------------------------------------------------------------------------
# PHASE 2 — COLLECTION PLAN
# ---------------------------------------------------------------------------

def run_plan(state: dict) -> dict:
    banner("PHASE 2: COLLECTION PLAN", "=")

    bible_path = state.get("bible_path", "References/bible.md")
    best_score = state.get("collection_plan_score", 0.0)
    iteration = state.get("plan_iteration", 0)

    for i in range(iteration + 1, MAX_PLAN_ITERS + 1):
        banner(f"Plan Iteration {i}", "-")
        state["plan_iteration"] = i

        # Generate collection plan
        step("Generating collection plan...")
        uv_run(f"gen_collection_plan.py {bible_path}", timeout=600)

        # Count stories planned
        total_stories = get_total_stories(state)
        state["stories_total"] = total_stories
        step(f"Stories planned: {total_stories}")

        # Evaluate the plan (use bible validation as a proxy for now —
        # the plan quality is assessed by the orchestrator checking story count
        # and coverage. A dedicated plan evaluator could be added later.)
        plan_path = BASE_DIR / "collection_plan.md"
        if plan_path.exists():
            plan_text = plan_path.read_text()
            plan_word_count = len(plan_text.split())

            # Basic quality checks
            has_stories = total_stories >= 6
            has_echoes = "thematic" in plan_text.lower() or "echo" in plan_text.lower()
            has_briefs = plan_text.count("**Dramatic question:**") >= 4

            if has_stories and has_briefs:
                score = 7.5  # Reasonable plan
                if has_echoes:
                    score = 8.0
            elif has_stories:
                score = 6.0
            else:
                score = 4.0

            step(f"Plan quality estimate: {score} "
                 f"({total_stories} stories, {plan_word_count} words)")
        else:
            score = 0.0
            step("ERROR: collection_plan.md not generated")

        if score > best_score:
            commit_hash = git_add_commit(
                f"plan iter {i}: {total_stories} stories, score ~{score}")
            log_result(commit_hash, "plan", score, 0, "keep",
                       f"Iteration {i}: plan improved {best_score} -> {score}")
            best_score = score
            state["collection_plan_score"] = score
            save_state(state)
        else:
            step(f"Plan did not improve ({score} <= {best_score}), discarding")
            git_reset_hard("HEAD")
            log_result("discarded", "plan", score, 0, "discard",
                       f"Iteration {i}: no improvement")

        if best_score >= PLAN_THRESHOLD:
            step(f"Plan score {best_score} >= {PLAN_THRESHOLD} — PASSED")
            break
    else:
        step(f"WARNING: max iterations ({MAX_PLAN_ITERS}) reached "
             f"with score {best_score}")

    state["phase"] = "drafting"
    save_state(state)

    banner(f"PLAN COMPLETE — {state['stories_total']} stories planned, "
           f"score {best_score}")
    return state


# ---------------------------------------------------------------------------
# PHASE 3 — DRAFTING + PER-STORY REVISION
# ---------------------------------------------------------------------------

def run_drafting(state: dict) -> dict:
    banner("PHASE 3: DRAFTING + REVISION", "=")

    total = get_total_stories(state)
    start_story = state.get("stories_drafted", 0) + 1

    STORIES_DIR.mkdir(exist_ok=True)

    for st in range(start_story, total + 1):
        banner(f"Story {st}/{total}", "-")
        drafted = False

        for attempt in range(1, MAX_STORY_ATTEMPTS + 1):
            step(f"Attempt {attempt}/{MAX_STORY_ATTEMPTS}")

            # Generate characters
            step(f"Generating characters for Story {st}...")
            uv_run(f"gen_story_characters.py {st}", timeout=180)

            # Draft
            draft_result = uv_run(f"draft_story.py {st}", timeout=600)
            if draft_result.returncode != 0:
                step(f"Draft failed (exit {draft_result.returncode}), retrying...")
                continue

            st_file = STORIES_DIR / f"story_{st:02d}.md"
            if not st_file.exists() or st_file.stat().st_size < 100:
                step("Story file missing or too short, retrying...")
                continue

            word_count = len(st_file.read_text().split())
            step(f"Drafted {word_count} words")

            # Evaluate
            eval_result = uv_run(f"evaluate.py --story={st}", timeout=300)
            score = parse_score(eval_result.stdout, "overall_score")
            step(f"Story {st} score: {score}")

            if score >= STORY_THRESHOLD:
                # Run adversarial edit + apply cuts
                step("Running adversarial edit...")
                uv_run(f"adversarial_edit.py story {st}", timeout=300)

                apply_cuts = BASE_DIR / "apply_cuts.py"
                if apply_cuts.exists():
                    step("Applying mechanical cuts...")
                    run_tool(f"uv run python apply_cuts.py story {st} "
                             "--types OVER-EXPLAIN REDUNDANT", timeout=120)

                commit_hash = git_add_commit(
                    f"story{st:02d}: score {score}, {word_count}w")
                log_result(commit_hash, f"story{st:02d}", score, word_count,
                           "keep", f"Story {st} (attempt {attempt})")
                state["stories_drafted"] = st
                save_state(state)
                drafted = True
                break
            else:
                step(f"Score {score} < {STORY_THRESHOLD}, retrying...")
                log_result("discarded", f"story{st:02d}", score, word_count,
                           "discard", f"Story {st} attempt {attempt}")

        if not drafted:
            step(f"WARNING: Story {st} failed all attempts, keeping last")
            st_file = STORIES_DIR / f"story_{st:02d}.md"
            if st_file.exists():
                word_count = len(st_file.read_text().split())
                commit_hash = git_add_commit(
                    f"story{st:02d}: best-effort after {MAX_STORY_ATTEMPTS} attempts")
                log_result(commit_hash, f"story{st:02d}", "?", word_count,
                           "forced", f"Story {st}: kept after max attempts")
                state["stories_drafted"] = st
                save_state(state)

    state["phase"] = "polish"
    state["stories_drafted"] = total
    save_state(state)

    total_words = count_words_in_stories()
    banner(f"DRAFTING COMPLETE — {total} stories, {total_words} words")
    return state


# ---------------------------------------------------------------------------
# PHASE 4 — COLLECTION POLISH + EXPORT
# ---------------------------------------------------------------------------

def run_polish(state: dict) -> dict:
    banner("PHASE 4: COLLECTION POLISH + EXPORT", "=")

    BRIEFS_DIR.mkdir(exist_ok=True)
    EDIT_LOGS_DIR.mkdir(exist_ok=True)

    # 1. Collection-level evaluation
    step("Evaluating collection...")
    eval_result = uv_run("evaluate.py --collection", timeout=600)
    collection_score = parse_score(eval_result.stdout, "collection_score")
    weakest_story = parse_score(eval_result.stdout, "weakest_story")

    step(f"Collection score: {collection_score}")
    state["collection_score"] = collection_score

    # 2. Revise weakest story if identified
    if weakest_story > 0:
        ws = int(weakest_story)
        step(f"Weakest story: {ws} — running targeted revision...")

        # Pre-score
        pre_eval = uv_run(f"evaluate.py --story={ws}", timeout=300)
        pre_score = parse_score(pre_eval.stdout, "overall_score")

        # Generate brief and revise
        gen_brief = BASE_DIR / "gen_brief.py"
        if gen_brief.exists():
            step(f"Generating revision brief for Story {ws}...")
            run_tool(f"uv run python gen_brief.py --story-eval {ws}", timeout=300)

            brief_candidates = sorted(
                BRIEFS_DIR.glob(f"story{ws:02d}*.md"),
                key=lambda p: p.stat().st_mtime, reverse=True)
            if brief_candidates:
                brief_file = brief_candidates[0]
                step(f"Revising Story {ws} with brief {brief_file.name}...")
                uv_run(f"gen_revision.py story {ws} {brief_file}", timeout=600)

                # Post-score
                post_eval = uv_run(f"evaluate.py --story={ws}", timeout=300)
                post_score = parse_score(post_eval.stdout, "overall_score")
                step(f"Story {ws}: {pre_score} -> {post_score}")

                if post_score >= pre_score:
                    git_add_commit(
                        f"polish: story{ws:02d} revised {pre_score}->{post_score}")
                else:
                    step("Revision regressed, reverting")
                    git_reset_hard("HEAD")

    # 3. Build manuscript
    step("Building collection manuscript...")
    stories = sorted(STORIES_DIR.glob("story_*.md"))
    stories = [s for s in stories if "_characters" not in s.name]

    parts = []
    for st_file in stories:
        text = st_file.read_text().strip()
        if text:
            parts.append(text)

    if parts:
        manuscript = BASE_DIR / "manuscript.md"
        manuscript.write_text("\n\n---\n\n".join(parts) + "\n")
        total_words = sum(len(p.split()) for p in parts)
        step(f"Manuscript: {len(parts)} stories, {total_words} words")
    else:
        step("WARNING: no story files found for manuscript")

    # 4. Final commit
    commit_hash = git_add_commit("export: collection manuscript")
    total_words = count_words_in_stories()
    log_result(commit_hash, "export", state.get("collection_score", "?"),
               total_words, "export", "Collection export")

    state["phase"] = "complete"
    save_state(state)

    banner(f"COLLECTION COMPLETE — {len(parts)} stories, {total_words} words, "
           f"score {collection_score}")
    return state


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(args):
    if args.from_scratch:
        banner("STARTING FROM SCRATCH")
        state = default_state()
        if args.bible:
            state["bible_path"] = args.bible
        save_state(state)
    else:
        state = load_state()
        if args.bible:
            state["bible_path"] = args.bible
            save_state(state)

    # Ensure directories exist
    STORIES_DIR.mkdir(exist_ok=True)
    BRIEFS_DIR.mkdir(exist_ok=True)
    EDIT_LOGS_DIR.mkdir(exist_ok=True)
    EVAL_LOGS_DIR.mkdir(exist_ok=True)

    # Determine which phases to run
    if args.phase:
        phases = [args.phase]
    else:
        current = state.get("phase", "intake")
        if current == "complete":
            print("Pipeline already complete. Use --from-scratch to restart "
                  "or --phase to run a specific phase.")
            return
        try:
            start_idx = PHASE_ORDER.index(current)
        except ValueError:
            start_idx = 0
        phases = PHASE_ORDER[start_idx:]

    banner(f"COLLECTION PIPELINE — phases: {', '.join(phases)}")
    print(f"  State: phase={state.get('phase')}, "
          f"bible_score={state.get('bible_score', 0)}, "
          f"stories={state.get('stories_drafted', 0)}/{state.get('stories_total', '?')}, "
          f"collection_score={state.get('collection_score', 0)}")

    start_time = datetime.now()

    for phase in phases:
        try:
            if phase == "intake":
                state = run_intake(state)
            elif phase == "plan":
                state = run_plan(state)
            elif phase == "drafting":
                state = run_drafting(state)
            elif phase == "polish":
                state = run_polish(state)
            else:
                print(f"Unknown phase: {phase}")
                sys.exit(1)
        except KeyboardInterrupt:
            banner("INTERRUPTED — state saved")
            save_state(state)
            sys.exit(130)
        except Exception as e:
            print(f"\n  FATAL ERROR in {phase}: {e}")
            save_state(state)
            raise

    elapsed = datetime.now() - start_time
    hours = elapsed.total_seconds() / 3600

    banner("PIPELINE COMPLETE")
    print(f"  Time:       {hours:.1f} hours")
    print(f"  Phase:      {state.get('phase')}")
    print(f"  Bible:      {state.get('bible_score', 0)}")
    print(f"  Stories:    {state.get('stories_drafted', 0)}/{state.get('stories_total', '?')}")
    print(f"  Words:      {count_words_in_stories()}")
    print(f"  Collection: {state.get('collection_score', 0)}")


def main():
    parser = argparse.ArgumentParser(
        description="Short story collection pipeline — bible to finished collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python run_collection_pipeline.py                          # resume from current state
  python run_collection_pipeline.py --from-scratch           # start fresh
  python run_collection_pipeline.py --phase intake           # run only intake
  python run_collection_pipeline.py --phase plan             # run only planning
  python run_collection_pipeline.py --phase drafting         # run only drafting
  python run_collection_pipeline.py --phase polish           # run only polish
  python run_collection_pipeline.py --bible path/to/bible.md # specify bible
""")

    parser.add_argument(
        "--from-scratch", action="store_true",
        help="Reset state and start fresh")
    parser.add_argument(
        "--phase", choices=PHASE_ORDER,
        help="Run only a specific phase")
    parser.add_argument(
        "--bible", type=str, default=None,
        help="Path to the timeline bible (default: References/bible.md)")

    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
