"""
Score the reconciled blind coding workbooks against the production LLM codes.

Inputs, per corpus:
  the coded IRR workbook (Consensus tab): both raters' codes plus the
      reconciled final_code — raters coded and reconciled blind to the LLM code;
  the manifest answer key: unit_id -> production deeper code (pass 2, seed 2).

Reports Cohen's kappa with raw agreement for every rater/consensus/LLM pair.
The primary validation number is consensus (final_code) vs LLM. The sample is
STRATIFIED (balanced over the four codes, not corpus prevalence), so raw
agreement should be read alongside kappa.

Output: irr24_<corpus>_scored.xlsx — the joined table plus a
consensus_vs_llm_disagreements sheet.

Usage:  python3 score_irr_24.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "modified_data"
OUT = HERE.parent / "output"
CODES = ["addiction", "attachment", "both", "neither"]

CORPORA = {
    "legal": {
        "coded": "CODED Legal IRR v8 24cases STRATIFIED N150.xlsx",
        "manifest": "_manifest_legal_irr24.xlsx",
    },
    "media": {
        "coded": "CODED Media IRR v8 24cases STRATIFIED N150.xlsx",
        "manifest": "_manifest_media_irr24.xlsx",
    },
}


def norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


def score(corpus: str, cfg: dict) -> pd.DataFrame:
    cons = pd.read_excel(DATA / cfg["coded"], sheet_name="Consensus")
    man = pd.read_excel(DATA / cfg["manifest"])

    text_col = "text" if "text" in cons.columns else "para_text"
    keep = ["row", "unit_id", text_col, "code_rater1", "justification_rater1",
            "code_rater2", "justification_rater2", "notes_rater1", "notes_rater2",
            "agreement", "final_code"]
    if "headline" in cons.columns:
        keep.insert(2, "headline")
    cons = cons[keep].rename(columns={text_col: "text"}).copy()
    for c in ["code_rater1", "code_rater2", "final_code"]:
        cons[c] = norm(cons[c])

    # Verify the sheet is complete and every code is a legal label.
    assert len(cons) == 150, f"{corpus}: expected 150 rows, got {len(cons)}"
    for c in ["code_rater1", "code_rater2", "final_code"]:
        bad = cons.loc[~cons[c].isin(CODES), ["row", "unit_id", c]]
        assert bad.empty, f"{corpus}: non-label values in {c}:\n{bad}"

    # final_code must equal the shared code wherever the raters agreed.
    agreed = cons[cons.code_rater1 == cons.code_rater2]
    drift = agreed[agreed.final_code != agreed.code_rater1]
    assert drift.empty, f"{corpus}: final_code differs where raters agreed:\n{drift}"

    # The manifest's deeper_meaning is both the production code and the stratum;
    # its reasoning string is the LLM's justification, needed to diagnose
    # disagreements against the human justifications.
    m = cons.merge(man[["unit_id", "deeper_meaning", "reasoning"]]
                   .rename(columns={"reasoning": "llm_reasoning"}),
                   on="unit_id", validate="one_to_one")
    assert len(m) == 150, f"{corpus}: manifest join lost rows"
    m["deeper_meaning"] = norm(m["deeper_meaning"])

    def pair(a: str, b: str) -> tuple[float, float]:
        return (cohen_kappa_score(m[a], m[b], labels=CODES),
                (m[a] == m[b]).mean())

    print(f"\n{corpus.upper()} (N=150, stratified)")
    print("agreement (Cohen's kappa, raw %):")
    for name, a, b in [("Rater1 vs Rater2", "code_rater1", "code_rater2"),
                       ("consensus vs LLM", "final_code", "deeper_meaning"),
                       ("Rater1 vs LLM", "code_rater1", "deeper_meaning"),
                       ("Rater2 vs LLM", "code_rater2", "deeper_meaning")]:
        k, raw = pair(a, b)
        print(f"  {name}: kappa={k:.3f}  raw={raw:.1%}")

    print("per-class (consensus vs LLM): one-vs-rest kappa, raw within stratum:")
    for c in CODES:
        k = cohen_kappa_score(m["final_code"] == c, m["deeper_meaning"] == c)
        cell = m[m.deeper_meaning == c]  # stratum = production code
        raw = (cell.final_code == cell.deeper_meaning).mean()
        print(f"  {c}: kappa={k:.3f}  raw={raw:.1%} (n={len(cell)})")

    disagreements = m[m.final_code != m.deeper_meaning]
    out = OUT / f"irr24_{corpus}_scored.xlsx"
    with pd.ExcelWriter(out) as xw:
        m.to_excel(xw, sheet_name="scored", index=False)
        disagreements.to_excel(xw, sheet_name="consensus_vs_llm_disagreements",
                               index=False)
    print(f"wrote {out.name} ({len(disagreements)} consensus-vs-LLM disagreements)")
    return m


def main() -> None:
    for corpus, cfg in CORPORA.items():
        score(corpus, cfg)


if __name__ == "__main__":
    main()
