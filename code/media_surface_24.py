#!/usr/bin/env python3
"""
Surface (vocabulary) pass over the media corpus. Deterministic, no API calls.

Restricts to the coding set (usable, non-duplicate articles), builds the
unit_id join key (<pdf>#u<unit_seq>), and assigns surface_meaning from
addict*/attach* word-stem counts.

Input:  ../1_extraction/media_units/media_CODED_paragraphs_24.xlsx
Output: media_paragraphs_24.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))
from media_dictionary_pass import add_surface                # noqa: E402

CORPUS = ROOT / "modified_data" / "media_CODED_paragraphs_24.xlsx"
OUTPUT = ROOT / "output" / "media_paragraphs_24.xlsx"


def main() -> None:
    df = pd.read_excel(CORPUS)
    print(f"Read {len(df):,} units from {CORPUS.name} ({df['pdf'].nunique()} PDFs)")

    keep = df["article_usable"] & ~df["is_duplicate"]
    df = df[keep].copy()
    print(f"Coding set (usable & not duplicate): {len(df):,} paragraphs, "
          f"{df.groupby('pdf')['article_seq'].nunique().sum()} articles")

    assert not df.duplicated(["pdf", "unit_seq"]).any(), \
        "(pdf, unit_seq) is not unique in the coding set"
    df["unit_id"] = df["pdf"].astype(str) + "#u" + df["unit_seq"].astype(str)
    assert df["unit_id"].is_unique

    df = add_surface(df, df["para_text"].fillna("").tolist())

    df.to_excel(OUTPUT, index=False)
    print(f"\nWrote {OUTPUT.name}  ({len(df):,} rows)")
    print("\nsurface_meaning:")
    print(df["surface_meaning"].value_counts().to_string())
    print("\nby label (headlines are coded units now):")
    print(pd.crosstab(df["label"], df["surface_meaning"]).to_string())
    print("\nsurface by PDF (substantive only):")
    sub = df[df["surface_meaning"] != "neither"]
    print(pd.crosstab(sub["pdf"], sub["surface_meaning"]).to_string())


if __name__ == "__main__":
    main()
