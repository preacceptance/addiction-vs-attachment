#!/usr/bin/env python3
"""
Re-bake the coding manuals into the LLM-pass prompt constants.

The coding manuals live as .docx files but the LLM passes use them as prompt
string CONSTANTS baked into the code (not read at runtime, so the pass is a
frozen artifact). This script keeps the two in sync: run it after ANY edit to
either docx.

For each corpus it:
  1. extracts the docx text verbatim (pandoc --track-changes=accept --wrap=none),
  2. appends the shared OUTPUT footer,
  3. enforces the ONE-BOUNDARY invariant — the legal and media prompts must be
     byte-identical except the title line and the genre intro clause,
  4. splices the result into the prompt constant:
       • code/llm_pass_v2.py     LEGAL_CODING_SYSTEM        (legal)
       • code/media_llm_pass.py  MEDIA_CODING_SYSTEM  (media)

If the invariant is violated (e.g. an edit to one docx wasn't mirrored in the
other) it aborts WITHOUT writing, so the two corpora can never silently drift.

Provenance comments above each constant are maintained by hand — update the
version/date there when the source docx changes.

Usage:  python3 code/dev/bake_manuals.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEGAL_DOCX = ROOT / "Coding_Instructions_v7_Legal_Final.docx"
MEDIA_DOCX = ROOT / "Coding_Instructions_v7_Media_Final.docx"

# Shared footer appended to both prompts (identical → preserves the one-boundary
# invariant). Lists the named criteria (numbered by doc order) and requires the
# reasoning to lead with the exact criterion invoked — mirrors the few-shots.
FOOTER = ('\n\nNAMED CRITERIA — when you code Addiction, Attachment, or Both, cite the exact criterion/criteria you are invoking:\n'
          '  Addiction: 1. Explicit addiction vocabulary; 2. Impaired control; 3. Social impairment; 4. Risky use; 5. Biological mechanisms; 6. Tolerance and withdrawal.\n'
          '  Attachment: 1. Explicit attachment vocabulary; 2. Proximity maintenance; 3. Separation distress; 4. Safe haven; 5. Secure base.\n'
          '\nOUTPUT\n'
          '  deeper_meaning: one of "addiction", "attachment", "both", "neither"\n'
          '  reasoning: lead with the exact named criterion/criteria invoked (e.g., "2. Proximity maintenance — ..."); for Neither, no criterion applies')


def extract(docx: Path) -> str:
    if not docx.exists():
        sys.exit(f"ERROR: manual not found: {docx}")
    out = subprocess.run(
        ["pandoc", "--track-changes=accept", "-t", "plain", "--wrap=none", str(docx)],
        capture_output=True, text=True, check=True).stdout
    return out.rstrip("\n")


def splice(pyfile: Path, const_name: str, new_body: str) -> None:
    src = pyfile.read_text()
    const = f'{const_name} = """{new_body}"""'
    pattern = rf'^{const_name} = """.*?"""'
    # function replacement (not a string) so backslashes/quotes in the manual
    # are inserted literally, never interpreted as regex escapes.
    new_src, n = re.subn(pattern, lambda m: const, src, count=1, flags=re.S | re.M)
    if n != 1:
        sys.exit(f"ERROR: matched {n} occurrences of {const_name} in {pyfile.name} (expected 1)")
    pyfile.write_text(new_src)
    print(f"  baked {const_name} into {pyfile.name}")


def main() -> None:
    legal = extract(LEGAL_DOCX) + FOOTER
    media = extract(MEDIA_DOCX) + FOOTER

    lg, md = legal.split("\n"), media.split("\n")
    if len(lg) != len(md):
        sys.exit(f"ERROR: prompts have different line counts ({len(lg)} vs {len(md)}) "
                 f"— not one boundary; check the docx edits.")
    diffs = [i for i, (a, b) in enumerate(zip(lg, md)) if a != b]
    if diffs != [0, 2]:
        sys.exit(f"ERROR: prompts differ on lines {diffs}; expected exactly [0, 2] "
                 f"(title + genre intro). An edit to one docx was not mirrored in the other.")
    print(f"one-boundary invariant OK: {len(lg)} lines, differ only on title + intro")

    splice(ROOT / "code" / "llm_pass_v2.py", "LEGAL_CODING_SYSTEM", legal)
    splice(ROOT / "code" / "media_llm_pass.py", "MEDIA_CODING_SYSTEM", media)
    print("done — re-validate on held-out rows before the production run.")


if __name__ == "__main__":
    main()
