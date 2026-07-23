#!/usr/bin/env python3
"""
Media step 2 — surface (vocabulary) pass; adds surface columns IN PLACE to both
media_articles.xlsx and media_paragraphs.xlsx from media_extract.py.

Same narrow addict*/attach* stems as legal dictionary_pass.py; attach split into
procedural vs substantive (via procedural_attach), only substantive drives has_attach.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from procedural_attach import classify_attach_hits

ROOT  = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "media_cleaned_texts"
MEDIA_ARTICLES   = ROOT / "modified_data" / "media_articles.xlsx"   # local only
MEDIA_PARAGRAPHS = ROOT / "modified_data" / "media_paragraphs.xlsx"
ADDICT_RE = re.compile(r'\baddict\w*\b', re.IGNORECASE)


def dict_flags(text: str) -> tuple[int, int, int, int]:
    # attach hits split procedural vs substantive; only substantive counts as attachment.
    addict = len(ADDICT_RE.findall(text))
    total, proc, sub = classify_attach_hits(text)
    return addict, total, proc, sub


def add_surface(df: pd.DataFrame, texts: list[str]) -> pd.DataFrame:
    flags = [dict_flags(t) for t in texts]
    df["addict_hits"]             = [f[0] for f in flags]
    df["attach_hits"]             = [f[1] for f in flags]
    df["attach_hits_procedural"]  = [f[2] for f in flags]
    df["attach_hits_substantive"] = [f[3] for f in flags]
    df["has_addict"] = df["addict_hits"] > 0
    df["has_attach"] = df["attach_hits_substantive"] > 0
    # surface_meaning = which stem(s) present: addiction / attachment / both / neither.
    df["surface_meaning"] = "neither"
    df.loc[ df["has_addict"] & ~df["has_attach"], "surface_meaning"] = "addiction"
    df.loc[~df["has_addict"] &  df["has_attach"], "surface_meaning"] = "attachment"
    df.loc[ df["has_addict"] &  df["has_attach"], "surface_meaning"] = "both"
    return df


def main() -> None:
    # Surface labels are written to EVERY row (keep-everything-and-flag), but the
    # analytical unit is the UNIQUE-USABLE set: full articles with cross-search
    # duplicates removed (usable & ~is_duplicate). Duplicates carry identical text
    # so they get identical labels; we just don't count them twice. Report both.
    arts = pd.read_excel(MEDIA_ARTICLES)
    arts = add_surface(arts, [(CLEAN / fn).read_text(encoding="utf-8")
                              for fn in arts["filename"]])
    arts.to_excel(MEDIA_ARTICLES, index=False)
    aq = arts[arts["usable"] & ~arts["is_duplicate"]]
    print(f"{MEDIA_ARTICLES.name}  (all rows n={len(arts)}; unique-usable n={len(aq)})")
    print(aq["surface_meaning"].value_counts().to_string())

    pars = pd.read_excel(MEDIA_PARAGRAPHS)
    pars = add_surface(pars, pars["para_text"].astype(str).tolist())
    pars.to_excel(MEDIA_PARAGRAPHS, index=False)
    pq = pars[pars["article_usable"] & ~pars["is_duplicate"]]
    print(f"\n{MEDIA_PARAGRAPHS.name}  (all rows n={len(pars)}; unique-usable n={len(pq)})")
    print(pq["surface_meaning"].value_counts().to_string())


if __name__ == "__main__":
    main()
