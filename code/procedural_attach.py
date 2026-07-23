"""
Split attach* word hits into procedural (exhibits/pleadings, e.g. "attached
hereto", "Attachment A") vs substantive (psychological/parasocial attachment).

Public API: classify_attach_hits(text) -> (total, procedural, substantive).
"""
from __future__ import annotations
import re

ATTACH_PAT = re.compile(r"\battach\w*\b", re.IGNORECASE)

# Procedural cue *immediately after* the attach token.
PROCEDURAL_AFTER = re.compile(
    r"^\s*(?:"
    r"hereto|herewith|hereunder|"
    r"as\s+exhibit|as\s+exh\b|as\s+attachment|"
    r"(?:to|with)\s+(?:this|the|plaintiff'?s?|defendant'?s?)\s+"
    r"(?:complaint|petition|filing|document|motion|memorandum|declaration|"
    r"order|amended\s+complaint|first\s+amended\s+complaint|"
    r"second\s+amended\s+complaint|class\s+action\s+complaint)"
    r")\b",
    re.IGNORECASE,
)

# "Attachment A", "Attachment 1" — exhibit-style label, almost always procedural.
ATTACHMENT_LABEL_AFTER = re.compile(r"^\s+[A-Z0-9]\b")

# Procedural cue *before* the attach token: a clear exhibit/document subject
# that "is attached".  Limited to cases where the subject is unambiguous.
PROCEDURAL_BEFORE = re.compile(
    r"\b(?:exhibit|exh\.|attachment)\s+[A-Za-z0-9]+(?:[^.]{0,80}?)(?:is|are|was|were|being)\s*$",
    re.IGNORECASE,
)
# "true and correct cop(y|ies) ... is/are attached"
TRUE_CORRECT = re.compile(
    r"\btrue\s+and\s+correct\s+(?:copy|copies)\b[^.]{0,100}?(?:is|are|was|were|being)\s*$",
    re.IGNORECASE,
)


def is_procedural_match(text: str, m: re.Match) -> bool:
    # Decide procedural vs substantive from the words surrounding this one hit.
    word = m.group(0).lower()
    after  = text[m.end():m.end() + 100]
    before = text[max(0, m.start() - 120):m.start()]

    # "Attachment A" / "Attachment 1" style label.
    if word.startswith("attachment") and ATTACHMENT_LABEL_AFTER.match(after):
        return True
    # "attached hereto" / "attached as Exhibit" / "attached to this complaint"
    if PROCEDURAL_AFTER.match(after):
        return True
    # "Exhibit A is attached" / "true and correct copy is attached"
    if PROCEDURAL_BEFORE.search(before) or TRUE_CORRECT.search(before):
        return True
    return False


def classify_attach_hits(text: str) -> tuple[int, int, int]:
    """Return (total_hits, procedural_hits, substantive_hits)."""
    total = procedural = 0
    for m in ATTACH_PAT.finditer(text):
        total += 1
        if is_procedural_match(text, m):
            procedural += 1
    # Substantive = whatever is left over after removing procedural hits.
    return total, procedural, total - procedural
