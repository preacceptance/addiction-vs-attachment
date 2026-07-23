#!/usr/bin/env python3
"""Score the held-out IRR sample (legal + media) against the LLM's coding.

Each held-out paragraph has two independent human codes (code_itai, code_omkar)
and their reconciled consensus (final_code). Per corpus this reports:
  - each rater vs the LLM        (Itai-vs-LLM, Omkar-vs-LLM)
  - the two raters vs each other (the inter-human ceiling — the best the LLM could do)
  - the consensus vs the LLM     (the headline number)
  - Fleiss kappa across both raters + the LLM
Always report the per-rater numbers, not just consensus-vs-LLM.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent
CATS = ["addiction", "attachment", "both", "neither"]


def norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


def fleiss_kappa(codes: pd.DataFrame) -> float:
    # One column per rater; agreement across all raters on each row (subject).
    cats = sorted(set(codes.values.ravel()))
    counts = np.array([[(row == c).sum() for c in cats] for _, row in codes.iterrows()])
    n = counts.sum(axis=1)[0]
    p_i = ((counts ** 2).sum(axis=1) - n) / (n * (n - 1))
    p_e = ((counts.sum(axis=0) / counts.sum()) ** 2).sum()
    return (p_i.mean() - p_e) / (1 - p_e)


def kappa_line(name: str, a: pd.Series, b: pd.Series) -> str:
    return (f"  {name}: kappa={cohen_kappa_score(a, b):.3f}  "
            f"raw={(a == b).mean():.2f}  (n={len(a)})")


def score_corpus(label: str, manifest_path: Path, output_path: Path,
                 id_cols: list[str]) -> None:
    print(f"\n===== {label} =====")
    if not manifest_path.exists():
        print(f"  manifest missing ({manifest_path.name}) — skipping")
        return
    if not output_path.exists():
        print(f"  production output missing ({output_path.name}) — skipping")
        return

    man = pd.read_csv(manifest_path)
    out = pd.read_excel(output_path)
    # Guard: held-out rows must not have been used as few-shots (split contamination).
    if "is_fewshot" in out.columns:
        assert not out.merge(man[id_cols], on=id_cols)["is_fewshot"].any(), \
            "held-out rows flagged as few-shot — split contamination"

    # Join human codes (manifest) to LLM codes (production output) on unit keys.
    df = man.merge(out[id_cols + ["deeper_meaning"]], on=id_cols, how="left")
    df["llm"] = norm(df["deeper_meaning"])
    # Keep only rows the production pass actually coded.
    ok = df[df["llm"].isin(CATS)].copy()
    if ok.empty:
        print("  no production LLM codes for the held-out rows — rerun the "
              "corpus pass first")
        return
    if len(ok) < len(df):
        print(f"  ⚠ {len(df) - len(ok)} held-out rows lack production codes")

    for col in ["code_itai", "code_omkar", "final_code"]:
        ok[col] = norm(ok[col])

    print(f"  Held-out rows scored: {len(ok)}")
    print(kappa_line("Itai  vs LLM (blind)", ok["code_itai"], ok["llm"]))
    print(kappa_line("Omkar vs LLM (blind)", ok["code_omkar"], ok["llm"]))
    print(kappa_line("Itai  vs Omkar (inter-human baseline)",
                     ok["code_itai"], ok["code_omkar"]))
    print(kappa_line("Consensus vs LLM (headline)", ok["final_code"], ok["llm"]))
    print(f"  Fleiss (Itai+Omkar+LLM): "
          f"{fleiss_kappa(ok[['code_itai', 'code_omkar', 'llm']]):.3f}")
    print("\n  Consensus x LLM confusion:")
    print(pd.crosstab(ok["final_code"], ok["llm"]).to_string())


def score_v3_secondary() -> None:
    """The 30 v3 few-shot paragraphs (Itai single-coder), out-of-prompt since
    the current few-shots replaced them — secondary check only."""
    print("\n===== LEGAL secondary: v3-30 (Itai single-coder, out-of-prompt) =====")
    out_path = ROOT / "output" / "legal_paragraphs_llm.xlsx"
    if not out_path.exists():
        print("  production output missing — skipping")
        return
    fs = pd.read_excel(ROOT / "modified_data" / "legal_fewshot_v3.xlsx")
    out = pd.read_excel(out_path)
    if "is_fewshot" not in out.columns:
        print("  output predates the current few-shot config — skipping")
        return
    df = fs.merge(out[["case", "para_num", "deeper_meaning", "is_fewshot"]],
                  on=["case", "para_num"], how="left")
    df = df.drop_duplicates(subset=["case", "para_num"])
    # Only valid as a secondary check if these rows aren't in the prompt.
    assert not df["is_fewshot"].any(), "v3 rows overlap the few-shots"
    df["llm"] = norm(df["deeper_meaning"])
    df["itai"] = norm(df["code"])
    ok = df[df["llm"].isin(CATS)]
    if ok.empty:
        print("  no production codes yet — skipping")
        return
    print(kappa_line("Itai (v3-30) vs LLM", ok["itai"], ok["llm"]))
    print("  (single coder, class-coverage sample — context, not headline)")


def main() -> None:
    score_corpus("LEGAL (held-out 50)",
                 ROOT / "code" / "dev" / "_irr_gold50_manifest_legal.csv",
                 ROOT / "output" / "legal_paragraphs_llm.xlsx",
                 ["case", "para_seq"])
    score_v3_secondary()
    score_corpus("MEDIA (held-out 50)",
                 ROOT / "code" / "dev" / "_irr_gold50_manifest_media.csv",
                 ROOT / "output" / "media_paragraphs_llm.xlsx",
                 ["document_id", "para_idx"])


if __name__ == "__main__":
    main()
