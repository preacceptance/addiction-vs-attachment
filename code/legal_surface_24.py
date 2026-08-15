#!/usr/bin/env python3
"""
Surface (vocabulary) pass over the legal corpus. Deterministic, no API calls.

Counts addict*/attach* word stems in each coded paragraph, discards procedural
"attach" hits ("attached hereto as Exhibit A"), and assigns surface_meaning
(addiction / attachment / both / neither).

Input:  ../1_extraction/units/legal_CODED_paragraphs_24.xlsx
Output: legal_paragraphs_24.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))
from dictionary_pass import dict_flags, is_mangled          # noqa: E402

CORPUS = ROOT / "modified_data" / "legal_CODED_paragraphs_24.xlsx"
OUTPUT = ROOT / "output" / "legal_paragraphs_24.xlsx"


def main() -> None:
    df = pd.read_excel(CORPUS)
    print(f"Read {len(df):,} coded paragraphs from {CORPUS.name} "
          f"({df['case'].nunique()} cases)")

    # unit_id is the join key used by every downstream step; paragraph sequence
    # numbers are not stable identifiers, so unit_id must be unique and complete.
    assert df["unit_id"].is_unique, "unit_id is not unique in the coded corpus"
    assert df["unit_id"].notna().all(), "unit_id has blanks in the coded corpus"

    text = df["text"].fillna("")
    flags = text.map(dict_flags)
    df["addict_hits"]             = [f[0] for f in flags]
    df["attach_hits"]             = [f[1] for f in flags]
    df["attach_hits_procedural"]  = [f[2] for f in flags]
    df["attach_hits_substantive"] = [f[3] for f in flags]
    df["has_addict"] = df["addict_hits"] > 0
    # Procedural attach hits are exhibit bookkeeping, not the construct.
    df["has_attach"] = df["attach_hits_substantive"] > 0

    df["surface_meaning"] = "neither"
    df.loc[ df["has_addict"] & ~df["has_attach"], "surface_meaning"] = "addiction"
    df.loc[~df["has_addict"] &  df["has_attach"], "surface_meaning"] = "attachment"
    df.loc[ df["has_addict"] &  df["has_attach"], "surface_meaning"] = "both"

    # Flagged, never dropped. The LLM reads the raw text either way; this only
    # marks rows a human might want to eyeball.
    df["mangled"] = text.map(is_mangled)

    df.to_excel(OUTPUT, index=False)
    print(f"\nWrote {OUTPUT.name}  ({len(df):,} rows)")
    print("\nsurface_meaning:")
    print(df["surface_meaning"].value_counts().to_string())
    print(f"\nby label:")
    print(pd.crosstab(df["label"], df["surface_meaning"]).to_string())
    print(f"\nmangled (OCR/screenshot artefacts, flagged only): "
          f"{int(df['mangled'].sum())}")
    print("\nsurface by case (substantive only):")
    sub = df[df["surface_meaning"] != "neither"]
    print(pd.crosstab(sub["case"], sub["surface_meaning"]).to_string())


if __name__ == "__main__":
    main()
