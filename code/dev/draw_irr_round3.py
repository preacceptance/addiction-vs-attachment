#!/usr/bin/env python3
"""Draw the fresh stratified N=100 IRR samples (Round 3) per corpus.

Stratified 25/25/25/25 by PRODUCTION deeper_meaning (v5-simplified manual +
gold-100 few-shots). If a stratum has fewer than 25 available rows, all of it
is taken and the shortfall is redistributed evenly across the other strata
(same convention as Round 2 legal).

Exclusions (the sample must be untouched by any prior human coding or tuning):
  - gold-100 few-shot rows (is_fewshot in the production output)
  - v3-30 few-shot rows (legal_fewshot_v3.xlsx / media_fewshot_v3.xlsx)
  - media only: non-usable and duplicate paragraphs

Outputs per corpus:
  modified_data/{Legal,Media} IRR Round 3 N100 BLANK.xlsx
      sheets Itai + Omkar: id cols + para_text + code_<rater> + justification_<rater>
      (NO LLM codes anywhere in the workbook)
  code/dev/_irr_round3_manifest_{legal,media}.csv
      id cols + para_text + llm deeper_meaning (for scoring later; not for coders)

Usage: python3 code/dev/draw_irr_round3.py [legal|media|both]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEED = 20260611
CATS = ["addiction", "attachment", "both", "neither"]
N_PER_STRATUM = 25


def stratified_draw(pool: pd.DataFrame, seed: int) -> pd.DataFrame:
    pool = pool.copy()
    pool["_code"] = pool["deeper_meaning"].astype(str).str.strip().str.lower()
    pool = pool[pool["_code"].isin(CATS)]

    take = {c: N_PER_STRATUM for c in CATS}
    avail = {c: (pool["_code"] == c).sum() for c in CATS}
    short = {c: max(0, take[c] - avail[c]) for c in CATS}
    deficit = sum(short.values())
    if deficit:
        recipients = [c for c in CATS if short[c] == 0]
        for i, c in enumerate(sorted(recipients)):
            extra = deficit // len(recipients) + (1 if i < deficit % len(recipients) else 0)
            take[c] += extra
        for c in CATS:
            take[c] = min(take[c], avail[c]) if short[c] else take[c]
    print("  strata available:", avail, "→ taking:", {c: min(take[c], avail[c]) for c in CATS})

    parts = [pool[pool["_code"] == c].sample(n=min(take[c], avail[c]), random_state=seed)
             for c in CATS]
    out = pd.concat(parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    assert len(out) == 100, f"drew {len(out)}, expected 100"
    return out.drop(columns="_code")


def write_workbook(sample: pd.DataFrame, id_cols: list[str], out_xlsx: Path,
                   manifest_csv: Path) -> None:
    blank = sample[id_cols + ["para_text"]].copy()
    with pd.ExcelWriter(out_xlsx) as xw:
        for rater in ["Itai", "Omkar"]:
            sheet = blank.copy()
            sheet[f"code_{rater.lower()}"] = ""
            sheet[f"justification_{rater.lower()}"] = ""
            sheet.to_excel(xw, sheet_name=rater, index=False)
    sample[id_cols + ["para_text", "deeper_meaning"]].to_csv(manifest_csv, index=False)
    print(f"  wrote {out_xlsx.name} + {manifest_csv.name}")


def draw_legal() -> None:
    print("LEGAL Round 3 draw")
    out = pd.read_excel(ROOT / "output" / "legal_paragraphs_llm.xlsx")
    v3 = pd.read_excel(ROOT / "modified_data" / "legal_fewshot_v3.xlsx")
    v3_keys = set(zip(v3["case"], v3["para_num"]))
    pool = out[~out["is_fewshot"]
               & ~pd.Series([(c, p) in v3_keys for c, p in
                             zip(out["case"], out["para_num"])], index=out.index)]
    sample = stratified_draw(pool, SEED)
    write_workbook(sample, ["case", "para_num", "para_seq"],
                   ROOT / "modified_data" / "Legal IRR Round 3 N100 BLANK.xlsx",
                   ROOT / "code" / "dev" / "_irr_round3_manifest_legal.csv")


def draw_media() -> None:
    print("MEDIA Round 3 draw")
    out = pd.read_excel(ROOT / "output" / "media_paragraphs_llm.xlsx")
    if "is_fewshot" not in out.columns:
        raise SystemExit("media output predates gold-100 config — rerun media pass first")
    v3 = pd.read_excel(ROOT / "modified_data" / "media_fewshot_v3.xlsx")
    v3_keys = set(zip(v3["document_id"], v3["para_idx"]))
    pool = out[out["article_usable"] & ~out["is_duplicate"] & ~out["is_fewshot"]
               & ~pd.Series([(d, p) in v3_keys for d, p in
                             zip(out["document_id"], out["para_idx"])], index=out.index)]
    sample = stratified_draw(pool, SEED)
    write_workbook(sample, ["document_id", "para_idx"],
                   ROOT / "modified_data" / "Media IRR Round 3 N100 BLANK.xlsx",
                   ROOT / "code" / "dev" / "_irr_round3_manifest_media.csv")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("legal", "both"):
        draw_legal()
    if which in ("media", "both"):
        draw_media()
