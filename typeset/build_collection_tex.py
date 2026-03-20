#!/usr/bin/env python3
"""
Build LaTeX source from short story collection files.

Usage: python typeset/build_collection_tex.py

Output: typeset/stories_content.tex (to be included by a LaTeX template)
"""
import re
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
STORIES_DIR = BASE_DIR / "stories"
OUT_DIR = Path(__file__).parent


def latex_escape(t):
    t = t.replace('&', '\\&')
    t = t.replace('%', '\\%')
    t = t.replace('$', '\\$')
    t = t.replace('#', '\\#')
    t = t.replace('_', '\\_')
    return t


def md_to_latex(body):
    result = []
    for line in body.split('\n'):
        s = line.strip()
        if s == '---':
            result.append('\n\\scenebreak\n')
        elif s == '':
            result.append('')
        else:
            s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\\textit{\1}', s)
            s = latex_escape(s)
            s = s.replace('\u2014', '---')
            s = s.replace('\u2013', '--')
            s = s.replace('\u201c', '``')
            s = s.replace('\u201d', "''")
            s = s.replace('\u2018', '`')
            s = s.replace('\u2019', "'")
            s = s.replace('\u2026', '\\ldots{}')
            s = re.sub(r'(?<=\s)"(?=\w)', '``', s)
            s = re.sub(r'^"(?=\w)', '``', s)
            s = re.sub(r'(?<=\w)"(?=[\s.,;:!?\-])', "''", s)
            s = re.sub(r'(?<=\w)"$', "''", s)
            s = re.sub(r'(?<=[\.\?\!])"', "''", s)
            s = re.sub(r'(?<=\s)"', '``', s)
            s = re.sub(r'"(?=\s)', "''", s)
            s = re.sub(r'^"', '``', s)
            result.append(s)
    return '\n'.join(result)


def make_drop_cap(latex_body):
    """Extract first paragraph and wrap first letter in lettrine."""
    lines = latex_body.split('\n')
    first_para = []
    rest_start = 0
    found = False

    for i, l in enumerate(lines):
        if not found and l.strip():
            found = True
        if found:
            if l.strip() == '' or l.strip().startswith('\\scenebreak'):
                rest_start = i
                break
            first_para.append(l)
        else:
            rest_start = i + 1

    if not first_para:
        return latex_body

    para_text = ' '.join(first_para)
    rest = '\n'.join(lines[rest_start:])

    if len(para_text) < 2:
        return latex_body

    first_letter = para_text[0]
    after_first = para_text[1:]

    space_idx = after_first.find(' ')
    if space_idx > 0:
        word_rest = after_first[:space_idx]
        para_rest = after_first[space_idx:]
    else:
        word_rest = after_first
        para_rest = ""

    drop = f"\\lettrine[lines=2, lhang=0.1, nindent=0.2em]{{{first_letter}}}{{{word_rest}}}{para_rest}"
    return drop + '\n\n' + rest


def main():
    story_files = sorted(f for f in STORIES_DIR.glob("story_*.md")
                         if "_characters" not in f.name)

    if not story_files:
        print("ERROR: No stories found in stories/")
        return

    stories_tex = []
    for st_file in story_files:
        text = st_file.read_text()
        lines = text.strip().split('\n')

        # Extract title from first heading
        title_line = lines[0].lstrip('# ').strip() if lines else "Untitled"
        body = '\n'.join(lines[1:]).strip()

        latex_body = md_to_latex(body)
        latex_body = make_drop_cap(latex_body)

        # Use \chapter* for unnumbered story titles (collection style)
        stories_tex.append(
            f"\\chapter*{{{latex_escape(title_line)}}}\n"
            f"\\addcontentsline{{toc}}{{chapter}}{{{latex_escape(title_line)}}}\n"
            f"\\markboth{{{latex_escape(title_line)}}}{{{latex_escape(title_line)}}}\n\n"
            f"{latex_body}\n"
        )

        wc = len(body.split())
        print(f"  {st_file.name}: {title_line} ({wc} words)")

    content = '\n\\clearpage\n\n'.join(stories_tex)

    out_path = OUT_DIR / "stories_content.tex"
    out_path.write_text(content)
    print(f"\nWrote {len(stories_tex)} stories to {out_path}")


if __name__ == "__main__":
    main()
