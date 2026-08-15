#!/usr/bin/env python3
"""
Bake the two coding manuals into the LLM pass scripts as prompt constants.

Extracts each manual .docx verbatim (pandoc, tracked changes accepted),
appends the shared output-format footer, and REFUSES to write unless the two
prompts are identical except for the title line and the genre intro clause —
the two corpora must be coded against the same rules. Then splices:

    Coding_Instructions_v9_Legal_final.docx -> legal_llm_24.py  LEGAL_CODING_SYSTEM
    Coding_Instructions_v9_Media_final.docx -> media_llm_24.py  MEDIA_CODING_SYSTEM

The EXPECTED_CRITERIA check aborts if a manual stops naming a criterion the
footer lists, so the prompt never promises rules the manual doesn't contain.

Usage:  python3 new_data/rebuild_24/2_coding/bake_manuals_v9.py
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LEGAL_DOCX = ROOT / "Coding_Instructions_v9_Legal_final.docx"
MEDIA_DOCX = ROOT / "Coding_Instructions_v9_Media_final.docx"

FOOTER = (
    '\n\nNAMED CRITERIA — when you code Addiction, Attachment, or Both, cite the exact criterion/criteria you are invoking:\n'
    '  Addiction: 1. Explicit addiction vocabulary; 2. Impaired control; 3. Social impairment; 4. Risky use; 5. Biological mechanisms; 6. Tolerance and withdrawal.\n'
    '  Attachment: 1. Explicit attachment vocabulary; 2. Proximity maintenance; 3. Separation distress; 4. Safe haven; 5. Secure base; 6. Caregiving.\n'
    '\nOUTPUT\n'
    '  deeper_meaning: one of "addiction", "attachment", "both", "neither"\n'
    '  reasoning: lead with the exact named criterion/criteria invoked (e.g., "2. Proximity maintenance — ..."); for Neither, no criterion applies')

EXPECTED_CRITERIA = [
    "Explicit addiction vocabulary", "Impaired control", "Social impairment",
    "Risky use", "Biological mechanisms", "Tolerance and withdrawal",
    "Explicit attachment vocabulary", "Proximity maintenance",
    "Separation distress", "Safe haven", "Secure base", "Caregiving",
]


def extract(docx: Path) -> str:
    if not docx.exists():
        sys.exit(f"ERROR: manual not found: {docx}")
    out = subprocess.run(
        ["pandoc", "--track-changes=accept", "-t", "plain", "--wrap=none", str(docx)],
        capture_output=True, text=True, check=True).stdout
    return out.rstrip("\n")


def splice(pyfile: Path, const_name: str, new_body: str) -> None:
    src = pyfile.read_text()
    pattern = rf'^{const_name} = """.*?"""'
    const = f'{const_name} = """{new_body}"""'
    # function replacement (not a string) so backslashes/quotes in the manual
    # are inserted literally, never interpreted as regex escapes.
    new_src, n = re.subn(pattern, lambda m: const, src, count=1, flags=re.S | re.M)
    if n != 1:
        sys.exit(f"ERROR: matched {n} occurrences of {const_name} in "
                 f"{pyfile.name} (expected 1)")
    pyfile.write_text(new_src)
    print(f"  baked {const_name} into {pyfile.name}  ({len(new_body):,} chars)")


def main() -> None:
    legal = extract(LEGAL_DOCX) + FOOTER
    media = extract(MEDIA_DOCX) + FOOTER

    for name, body in (("legal", legal), ("media", media)):
        missing = [c for c in EXPECTED_CRITERIA if c not in body]
        if missing:
            sys.exit(f"ERROR: the {name} manual no longer names these criteria, "
                     "but the footer still lists them: " + ", ".join(missing))
    print(f"all {len(EXPECTED_CRITERIA)} named criteria present in both manuals")

    lg, md = legal.split("\n"), media.split("\n")
    if len(lg) != len(md):
        sys.exit(f"ERROR: prompts have different line counts ({len(lg)} vs "
                 f"{len(md)}) — not one boundary; check the docx edits.")
    diffs = [i for i, (a, b) in enumerate(zip(lg, md)) if a != b]
    if diffs != [0, 2]:
        sys.exit(f"ERROR: prompts differ on lines {diffs}; expected exactly "
                 f"[0, 2] (title + genre intro). An edit to one docx was not "
                 f"mirrored in the other.")
    print(f"one-boundary invariant OK: {len(lg)} lines, differ only on title + intro")

    splice(HERE / "legal_llm_24.py", "LEGAL_CODING_SYSTEM", legal)
    splice(HERE / "media_llm_24.py", "MEDIA_CODING_SYSTEM", media)
    print("done — the two corpora are now on the same v9 ruler.")


if __name__ == "__main__":
    main()
