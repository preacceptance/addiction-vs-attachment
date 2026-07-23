#!/usr/bin/env python3
"""
Step 2 — legal surface/vocabulary pass; edits legal_paragraphs.xlsx IN PLACE.

Counts narrow addict*/attach* stems, splits attach into procedural vs
substantive (only SUBSTANTIVE attach drives has_attach), sets surface_meaning.
Also flags OCR-mangled transcript/screenshot rows and writes cleaned_text
(manual repairs in cleaned_text are preserved across re-runs).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from procedural_attach import classify_attach_hits

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "modified_data" / "legal_paragraphs.xlsx"

ADDICT_RE = re.compile(r'\baddict\w*\b', re.IGNORECASE)


def dict_flags(text: str) -> tuple[int, int, int, int]:
    """Return (addict_hits, attach_total, attach_procedural, attach_substantive)."""
    addict_hits = len(ADDICT_RE.findall(text))
    total, procedural, substantive = classify_attach_hits(text)
    return addict_hits, total, procedural, substantive


# --- Mangled-text detection -------------------------------------------------
# Chat-transcript/screenshot exhibits were OCR'd upstream and extracted by a
# single-column-only text extractor, producing three garbage signatures:
#   zipper : two side-by-side columns interleaved char-by-char -> many lone letters
#   glued  : inter-word spaces dropped -> very long concatenated tokens
#   ts     : a transcript timestamp header glued to text ("AssistantonMay22,2025at..")
# Flagged (not dropped); paired with a `cleaned_text` column for manual repair.
_URL_RE = re.compile(r'https?://|www\.|\.com|\.org|\.gov|\.net|\.html|/')
_TS_GLUED_RE = re.compile(r'(?:assistant|user)\s*(?:on|at)\s*[A-Z][a-z]{2}\d', re.IGNORECASE)


def _glued_token_count(words: list[str]) -> int:
    n = 0
    for w in words:
        if _URL_RE.search(w) or "-" in w or any(c in w for c in "=?%&_"):
            continue
        core = re.sub(r"[^A-Za-z]", "", w)
        if len(core) >= 22 and len(core) / max(len(w), 1) >= 0.6:
            n += 1
    return n


def is_mangled(text: str) -> bool:
    words = str(text).split()
    n = len(words) or 1
    alpha_singles = sum(1 for w in words if len(w) == 1 and w.isalpha())
    zipper = (alpha_singles / n >= 0.15) and n >= 40
    return zipper or _glued_token_count(words) >= 2 or bool(_TS_GLUED_RE.search(str(text)))


# Trim a mangled row to its clean lead: keep prose up to the first OCR garbage,
# then drop the corrupted transcript/screenshot tail. This only fills `cleaned_text`,
# a reading/repair aid. The vocab counts and the LLM both use raw para_text, so
# nothing here changes a reported number.
_JUNK_CHARS = "_€®©]}{¥•⎯|)"
_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_APOS_MERGE_RE = re.compile(r"'[A-Za-z]{3,}")          
_DIGIT_FUSE_RE = re.compile(r"[A-Za-z]{2}\d|\d[A-Za-z]{2}")  
_ROLE_RE = re.compile(r"(?i)^(assistant|user)$")
_TRAIL_RE = re.compile(r"(?i)^(assistant\w*|user\w*|on|at|" + _MONTHS + r")[.,:]?$")


def _is_junk_token(tok: str) -> bool:
    if any(c in tok for c in _JUNK_CHARS):
        return True
    if len(re.sub(r"[^A-Za-z]", "", tok)) >= 16:
        return True
    return bool(_APOS_MERGE_RE.search(tok)) or bool(_DIGIT_FUSE_RE.search(tok))


def clean_lead(text: str) -> str:
    words = str(text).split()
    cut = len(words)
    for i, w in enumerate(words):
        window = words[i:i + 6]
        single_run = sum(1 for x in window if len(x) == 1 and x.isalpha()) >= 4
        role_header = _ROLE_RE.match(w) and i + 1 < len(words) and words[i + 1].lower() in ("on", "at")
        if _is_junk_token(w) or role_header or single_run:
            cut = i
            break
    lead = words[:cut]
    while lead and _TRAIL_RE.match(lead[-1]):     # strip trailing transcript-header remnants
        lead.pop()
    return " ".join(lead).strip()


def main() -> None:
    df = pd.read_excel(FILE)

    # Per-paragraph stem counts (addict + attach total/procedural/substantive).
    flags = df["para_text"].fillna("").map(dict_flags)
    df["addict_hits"]              = [f[0] for f in flags]
    df["attach_hits"]              = [f[1] for f in flags]
    df["attach_hits_procedural"]   = [f[2] for f in flags]
    df["attach_hits_substantive"]  = [f[3] for f in flags]
    df["has_addict"] = df["addict_hits"] > 0
    # Procedural attach hits (exhibits/pleadings) deliberately do NOT count.
    df["has_attach"] = df["attach_hits_substantive"] > 0

    # Four-way vocabulary subset from the two presence flags.
    df["surface_meaning"] = "neither"
    df.loc[ df["has_addict"] & ~df["has_attach"], "surface_meaning"] = "addiction"
    df.loc[~df["has_addict"] &  df["has_attach"], "surface_meaning"] = "attachment"
    df.loc[ df["has_addict"] &  df["has_attach"], "surface_meaning"] = "both"

    # Flag (do not drop) OCR-corrupted transcript/screenshot paragraphs.
    df["mangled"] = df["para_text"].fillna("").map(is_mangled)

    # cleaned_text: usable text for every row. Clean rows mirror para_text; mangled
    # rows are truncated to their clean lead (garbage tail dropped). Any existing
    # non-empty value (a manual repair) is preserved across re-runs. Nothing
    # downstream reads this column, so it never affects the numbers.
    if "cleaned_text" not in df.columns:
        df["cleaned_text"] = ""
    df["cleaned_text"] = df["cleaned_text"].fillna("").astype(str)
    df.loc[~df["mangled"], "cleaned_text"] = df.loc[~df["mangled"], "para_text"]
    blank_mangled = df["mangled"] & (df["cleaned_text"].str.strip() == "")
    df.loc[blank_mangled, "cleaned_text"] = df.loc[blank_mangled, "para_text"].fillna("").map(clean_lead)

    df.to_excel(FILE, index=False)
    print(f"Wrote surface columns → {FILE}  (n = {len(df)} paragraphs)")
    print("\nSubset counts:")
    print(df["surface_meaning"].value_counts().to_string())
    print(f"\nMangled paragraphs flagged: {int(df['mangled'].sum())} (cleaned_text = clean-lead truncation)")


if __name__ == "__main__":
    main()
