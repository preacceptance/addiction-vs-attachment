#!/usr/bin/env python3
"""
Step 1 — cleaned_texts/*.txt → legal_paragraphs.xlsx (one row per paragraph).

13/14 cases use numbered paragraphs; Soelberg v. OpenAI has no numbering, so it
falls back to blank-line-delimited prose (short chunks filtered as headings).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT        = Path(__file__).resolve().parent.parent
CLEANED_DIR = ROOT / "raw_data" / "cleaned_texts"
OUTPUT      = ROOT / "modified_data" / "legal_paragraphs.xlsx"

PROSE_MIN_WORDS = 15
NUMBERED_PARA_RE = re.compile(r'^(\d+)\.\s+(.*)')


def extract_numbered_paragraphs(text: str) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    current_num: int | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = NUMBERED_PARA_RE.match(line)
        if m:
            # New "N. …" line: flush the paragraph we were accumulating.
            if current_num is not None:
                body = " ".join(current_lines).strip()
                if body:
                    paragraphs.append((current_num, body))
            current_num = int(m.group(1))
            current_lines = [m.group(2).strip()]
        else:
            # Continuation (wrapped) line — append to the current paragraph.
            stripped = line.strip()
            if stripped and current_num is not None:
                current_lines.append(stripped)

    # Flush the final paragraph.
    if current_num is not None:
        body = " ".join(current_lines).strip()
        if body:
            paragraphs.append((current_num, body))

    return paragraphs


def extract_prose_paragraphs(text: str) -> list[tuple[int, str]]:
    # Soelberg fallback: split on blank lines, collapse whitespace, number 1..N.
    chunks = re.split(r'\n{2,}', text)
    paragraphs: list[tuple[int, str]] = []
    seq = 1
    for chunk in chunks:
        chunk = " ".join(chunk.split())
        # Drop short chunks (headings/captions).
        if len(chunk.split()) < PROSE_MIN_WORDS:
            continue
        paragraphs.append((seq, chunk))
        seq += 1
    return paragraphs


def process_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    case = path.stem

    # Prefer numbered paragraphs; fall back to prose only when none are found.
    numbered = extract_numbered_paragraphs(text)
    if numbered:
        pairs = numbered
        mode = "numbered"
    else:
        pairs = extract_prose_paragraphs(text)
        mode = "prose"

    print(f"  {case}: {len(pairs)} paragraphs [{mode}]")
    return [dict(case=case, para_num=n, para_text=t) for n, t in pairs]


def main() -> None:
    paths = sorted(CLEANED_DIR.glob("*.txt"))
    if not paths:
        raise SystemExit(f"No .txt files found in {CLEANED_DIR}")

    all_rows: list[dict] = []
    print("Extracting paragraphs…")
    for path in paths:
        all_rows.extend(process_file(path))

    df = pd.DataFrame(all_rows)
    # para_num is the complaint's literal number and RESTARTS per section/count,
    # so it is not unique within a case. para_seq is a document-order 1..N index
    # that IS unique per case — use (case, para_seq) as the row key.
    df.insert(2, "para_seq", df.groupby("case").cumcount() + 1)
    df.to_excel(OUTPUT, index=False)
    print(f"\nWrote {len(df)} paragraphs → {OUTPUT}")


if __name__ == "__main__":
    main()
