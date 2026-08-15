#!/usr/bin/env python3
"""
Within-model reliability for the legal corpus: Cohen's kappa between the two
independent coding passes (pass 1 seed 1, pass 2 seed 2). Few-shot rows are
excluded — they carry a human code copied identically into both passes, so
including them would inflate agreement. Also reports the flip table, the
headline attachment:addiction ratio computed from each pass independently,
and per-case agreement.

Inputs: legal_paragraphs_24_llm_v9p1.xlsx, legal_paragraphs_24_llm_v9p2.xlsx
Usage:  python3 within_llm_kappa_24.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

HERE = Path(__file__).resolve().parent
P1 = HERE.parent / "output" / "legal_paragraphs_24_llm_v9p1.xlsx"
P2 = HERE.parent / "output" / "legal_paragraphs_24_llm_v9p2.xlsx"
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

    w = p1[["unit_id", "case", "label", "surface_meaning", "is_fewshot",
            "deeper_meaning"]].merge(
        p2[["unit_id", "deeper_meaning"]], on="unit_id", suffixes=("_p1", "_p2"))
    assert len(w) == len(p1) == len(p2), \
        f"passes did not align on unit_id ({len(p1)}, {len(p2)}, merged {len(w)})"

    w = w[~w["is_fewshot"]].copy()
    a = w["deeper_meaning_p1"].astype(str).str.strip()
    b = w["deeper_meaning_p2"].astype(str).str.strip()

    k = cohen_kappa_score(a, b, labels=CATS)
    raw = (a == b).mean()
    print(f"WITHIN-LLM AGREEMENT — legal, 24 cases")
    print(f"  n = {len(w):,} paragraphs (38 few-shot rows excluded)")
    print(f"  Cohen's kappa = {k:.3f}      raw agreement = {raw:.1%}")

    print(f"\nHEADLINE RATIO, EACH PASS INDEPENDENTLY")
    print(f"  pass 1: {ratio(a)}")
    print(f"  pass 2: {ratio(b)}")

    print(f"\nFLIPS (rows where the two passes disagree)")
    d = a != b
    print(f"  {int(d.sum()):,} of {len(w):,} ({d.mean():.2%})")
    if d.any():
        print(pd.crosstab(a[d], b[d], rownames=["pass 1"],
                          colnames=["pass 2"]).to_string())
        print("\n  addiction <-> attachment flips (the ones that would move the "
              "headline claim):")
        cross = int(((a == "addiction") & (b == "attachment")).sum()
                    + ((a == "attachment") & (b == "addiction")).sum())
        print(f"    {cross}")

    print(f"\nPER-CASE (only cases with any disagreement)")
    per = w.assign(agree=~d).groupby("case")["agree"].agg(["mean", "size"])
    per = per[per["mean"] < 1].sort_values("mean")
    if len(per):
        for case, r in per.iterrows():
            print(f"  {case:<18} {r['mean']:.1%} agreement  ({int(r['size'])} paras)")
    else:
        print("  none")

    print(f"\nAGREEMENT BY LABEL (headings and footnotes are new to this corpus)")
    lab = w.assign(agree=~d).groupby("label")["agree"].agg(["mean", "size"])
    for label, r in lab.iterrows():
        print(f"  {label:<12} {r['mean']:.1%}  ({int(r['size']):,} paras)")


if __name__ == "__main__":
    main()
