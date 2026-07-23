#!/usr/bin/env python3
"""Score inter-rater reliability for the human validation samples.

For each corpus, two human coders independently coded the same stratified
sample of 150 paragraphs, blind to the LLM's codes, and then reconciled
their disagreements into a consensus code. This script joins the coded
workbook to the LLM-coded corpus file on paragraph keys (never row order),
verifies the join, and reports Cohen's kappa with raw agreement for every
pairing: coder vs coder, each coder vs LLM, and consensus vs LLM. The
validation number reported in the paper is consensus vs LLM.

The validation sample is stratified by LLM label (balanced across the four
codes rather than corpus prevalence), so raw agreement should be read
alongside kappa.

Writes output/irr_v7_{corpus}_scored.xlsx with a "scored" sheet (all rows,
all codes) and a "consensus_vs_llm_disagreements" sheet.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
CODES = ["addiction", "attachment", "both", "neither"]

CORPORA = {
    "legal": dict(
        coded=ROOT / "modified_data" / "CODED Legal IRR v7 STRATIFIED N150.xlsx",
        production=ROOT / "output" / "legal_paragraphs_llm.xlsx",
        keys=["case", "para_seq"],
        usable_filter=False,
    ),
    "media": dict(
        coded=ROOT / "modified_data" / "CODED fixed Media IRR v7 STRATIFIED N150.xlsx",
        production=ROOT / "output" / "media_paragraphs_llm.xlsx",
        keys=["document_id", "para_idx"],
        usable_filter=True,
    ),
}


def norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


def check(name: str, ok: bool, fails: list, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" [{detail}]" if detail else ""))
    if not ok:
        fails.append(name)


def score(corpus: str, cfg: dict) -> None:
    print(f"\n{'='*70}\n{corpus.upper()}\n{'='*70}")
    cons = pd.read_excel(cfg["coded"], sheet_name="Consensus")
    itai = pd.read_excel(cfg["coded"], sheet_name="Itai")
    omkar = pd.read_excel(cfg["coded"], sheet_name="Omkar")
    prod = pd.read_excel(cfg["production"])
    if cfg["usable_filter"]:
        prod = prod[prod["article_usable"] & ~prod["is_duplicate"]]
    keys = cfg["keys"]

    for df, cols in [(cons, ["code_itai", "code_omkar", "final_code"]),
                     (itai, ["code_itai"]), (omkar, ["code_omkar"])]:
        for c in cols:
            df[c] = norm(df[c])

    fails: list = []
    print("checks:")
    check("consensus has 150 unique-key rows",
          len(cons) == 150 and not cons.duplicated(keys).any(), fails)
    for sheet, col, who in [(itai, "code_itai", "Itai"), (omkar, "code_omkar", "Omkar")]:
        j = cons[keys + [col]].merge(sheet[keys + [col]], on=keys, suffixes=("_c", "_b"))
        check(f"{who} blind sheet matches consensus sheet",
              len(j) == 150 and (j[f"{col}_c"] == j[f"{col}_b"]).all(), fails)
    check("all codes valid",
          cons[["code_itai", "code_omkar", "final_code"]].isin(CODES).all().all(), fails)

    m = cons.merge(prod[keys + ["para_text", "deeper_meaning", "is_fewshot"]],
                   on=keys, how="left", suffixes=("", "_prod"))
    m["deeper_meaning"] = norm(m["deeper_meaning"])
    check("150/150 joined to an LLM code", m["deeper_meaning"].isin(CODES).all(), fails)
    check("paragraph text identical to production",
          (m["para_text"].astype(str) == m["para_text_prod"].astype(str)).all(), fails)
    check("no prompt-example rows in the sample", not m["is_fewshot"].any(), fails)
    m = m.drop(columns=["para_text_prod"])
    # A consensus code differing from both raters' blind codes is legitimate
    # (reconciliation can land on a third code) — surface it for eyeballing.
    stray = m[(m.final_code != m.code_itai) & (m.final_code != m.code_omkar)]
    for _, r in stray.iterrows():
        print(f"  NOTE  consensus differs from both raters: {tuple(r[k] for k in keys)} "
              f"itai={r.code_itai} omkar={r.code_omkar} final={r.final_code}")
    if fails:
        raise SystemExit(f"{corpus}: structural checks failed: {', '.join(fails)}")

    def pair(a: str, b: str) -> tuple[float, float]:
        return (cohen_kappa_score(m[a], m[b], labels=CODES), (m[a] == m[b]).mean())

    print("\nagreement (Cohen's kappa, raw %):")
    for name, a, b in [("Itai vs Omkar", "code_itai", "code_omkar"),
                       ("Itai vs LLM", "code_itai", "deeper_meaning"),
                       ("Omkar vs LLM", "code_omkar", "deeper_meaning"),
                       ("consensus vs LLM  << reported", "final_code", "deeper_meaning")]:
        k, raw = pair(a, b)
        print(f"  {name}: kappa={k:.3f}  raw={raw:.1%}")

    print("\nconfusion (consensus rows vs LLM cols):")
    print(pd.crosstab(m["final_code"], m["deeper_meaning"])
          .reindex(index=CODES, columns=CODES, fill_value=0))
    print("\nper-class kappa (consensus vs LLM, one-vs-rest):")
    for c in CODES:
        k = cohen_kappa_score(m["final_code"] == c, m["deeper_meaning"] == c)
        print(f"  {c:<10} {k:.3f}  (consensus n={int((m['final_code'] == c).sum())})")

    out = ROOT / "output" / f"irr_v7_{corpus}_scored.xlsx"
    disagreements = m[m.final_code != m.deeper_meaning]
    with pd.ExcelWriter(out) as xw:
        m.to_excel(xw, sheet_name="scored", index=False)
        disagreements.to_excel(xw, sheet_name="consensus_vs_llm_disagreements", index=False)
    print(f"\nwrote {out.name} ({len(disagreements)} consensus-vs-LLM disagreements)")


if __name__ == "__main__":
    for corpus, cfg in CORPORA.items():
        score(corpus, cfg)
    print("\ndone.")
