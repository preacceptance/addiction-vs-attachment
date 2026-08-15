#!/usr/bin/env python3
"""
Within-model reliability for the media corpus: Cohen's kappa between the two
independent coding passes (pass 1 seed 1, pass 2 seed 2).

Two differences from the legal script, both consequences of syndication:
  1. Kappa is computed over UNIQUE texts, not units — duplicate texts are
     coded once and the code propagated, so counting every copy would inflate
     agreement. The unit-level number is printed too, labelled as inflated.
  2. Excluded rows are the few-shot units AND their syndication copies
     (is_fewshot, is_fewshot_dup) — both carry a human code copied identically
     into both passes.

Inputs: media_paragraphs_24_llm_v9p1.xlsx, media_paragraphs_24_llm_v9p2.xlsx
Usage:  python3 media_within_llm_kappa_24.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

HERE = Path(__file__).resolve().parent
P1 = HERE.parent / "output" / "media_paragraphs_24_llm_v9p1.xlsx"
P2 = HERE.parent / "output" / "media_paragraphs_24_llm_v9p2.xlsx"
CATS = ["addiction", "attachment", "both", "neither"]


def ratio(codes: pd.Series) -> str:
    att = int((codes == "attachment").sum())
    add = int((codes == "addiction").sum())
    return f"{att} att / {add} add = {att / add:.2f}x" if add else f"{att} att / 0 add"


def main() -> None:
    for p in (P1, P2):
        if not p.exists():
            raise SystemExit(f"{p.name} not found — run both passes first.")

    p1 = pd.read_excel(P1)
    p2 = pd.read_excel(P2)

    w = p1[["unit_id", "pdf", "label", "text_key", "n_text_copies",
            "surface_meaning", "is_fewshot", "is_fewshot_dup",
            "deeper_meaning"]].merge(
        p2[["unit_id", "deeper_meaning"]], on="unit_id", suffixes=("_p1", "_p2"))
    assert len(w) == len(p1) == len(p2), \
        f"passes did not align on unit_id ({len(p1)}, {len(p2)}, merged {len(w)})"

    w = w[~w["is_fewshot"] & ~w["is_fewshot_dup"]].copy()
    a_units = w["deeper_meaning_p1"].astype(str).str.strip()
    b_units = w["deeper_meaning_p2"].astype(str).str.strip()

    # one row per unique text — the reported kappa
    u = w.drop_duplicates("text_key").copy()
    a = u["deeper_meaning_p1"].astype(str).str.strip()
    b = u["deeper_meaning_p2"].astype(str).str.strip()

    k = cohen_kappa_score(a, b, labels=CATS)
    raw = (a == b).mean()
    k_units = cohen_kappa_score(a_units, b_units, labels=CATS)
    print(f"WITHIN-LLM AGREEMENT — media, 24 cases")
    print(f"  n = {len(u):,} unique texts  ({len(w):,} units; few-shot rows and "
          f"their copies excluded)")
    print(f"  Cohen's kappa = {k:.3f}      raw agreement = {raw:.1%}")
    print(f"  (unit-level kappa = {k_units:.3f} — inflated by syndication "
          f"copies, do not report)")

    print(f"\nHEADLINE RATIO, EACH PASS INDEPENDENTLY (unit level, the corpus claim)")
    print(f"  pass 1: {ratio(a_units)}")
    print(f"  pass 2: {ratio(b_units)}")

    print(f"\nFLIPS (unique texts where the two passes disagree)")
    d = a != b
    print(f"  {int(d.sum()):,} of {len(u):,} ({d.mean():.2%})")
    if d.any():
        print(pd.crosstab(a[d], b[d], rownames=["pass 1"],
                          colnames=["pass 2"]).to_string())
        cross = int(((a == "addiction") & (b == "attachment")).sum()
                    + ((a == "attachment") & (b == "addiction")).sum())
        print("\n  addiction <-> attachment flips (the ones that would move the "
              f"headline claim):\n    {cross}")

    print(f"\nPER-PDF (unique texts; only PDFs with any disagreement)")
    du = u.assign(agree=(a == b))
    per = du.groupby("pdf")["agree"].agg(["mean", "size"])
    per = per[per["mean"] < 1].sort_values("mean")
    if len(per):
        for pdf, r in per.iterrows():
            print(f"  {pdf:<28} {r['mean']:.1%} agreement  ({int(r['size'])} texts)")
    else:
        print("  none")

    print(f"\nAGREEMENT BY LABEL (headlines are new to this corpus)")
    lab = du.groupby("label")["agree"].agg(["mean", "size"])
    for label, r in lab.iterrows():
        print(f"  {label:<12} {r['mean']:.1%}  ({int(r['size']):,} texts)")


if __name__ == "__main__":
    main()
