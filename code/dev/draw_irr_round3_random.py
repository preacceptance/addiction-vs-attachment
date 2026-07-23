#!/usr/bin/env python3
"""Round 3 IRR draw — RANDOM N=100 per corpus (decision 2026-06-11).

Supersedes the stratified draw_irr_round3.py (2026-06-10): stratification
required a completed LLM pass under the current config, so every config change
forced a full corpus re-run before a sample could be pulled. Random sampling
removes that dependency — drawn directly from the paragraph files, no LLM
codes involved at any point.

Pool & exclusions (2026-06-11 policy: ONLY the gold-100 few-shots are excluded —
they are in the prompt; the v3-30 are dissolved into the dataset):
  Legal: all 4,146 paragraphs minus gold-100 few-shots.
  Media: unique-usable pool (article_usable & ~is_duplicate) minus gold-100.

Outputs per corpus:
  modified_data/{Legal,Media} IRR Round 3 RANDOM N100.xlsx
      sheets Itai + Omkar: id cols + para_text + code_ + justification_ columns
  code/dev/_irr_round3_random_manifest_{legal,media}.csv
      id cols + para_text only (NO LLM codes — scoring joins to production
      output on the id keys later)

Seed 20260611. Expect ~85% surface-neither composition in legal — that is the
point of random sampling (representative, prevalence-realistic kappa).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEED = 20260611
N = 100


def write_workbook(sample: pd.DataFrame, id_cols: list[str], out_xlsx: Path,
                   manifest_csv: Path) -> None:
    blank = sample[id_cols + ["para_text"]].reset_index(drop=True)
    with pd.ExcelWriter(out_xlsx) as xw:
        for rater in ["Itai", "Omkar"]:
            sheet = blank.copy()
            sheet[f"code_{rater.lower()}"] = ""
            sheet[f"justification_{rater.lower()}"] = ""
            sheet.to_excel(xw, sheet_name=rater, index=False)
    blank.to_csv(manifest_csv, index=False)
    print(f"  wrote {out_xlsx.name} + {manifest_csv.name}")


def draw_legal() -> None:
    print("LEGAL Round 3 RANDOM draw")
    df = pd.read_excel(ROOT / "modified_data" / "legal_paragraphs.xlsx")
    gold = pd.read_excel(ROOT / "modified_data" / "legal_fewshot_gold100.xlsx")
    gold_keys = set(zip(gold["case"], gold["para_seq"]))
    excl = pd.Series([(c, p) in gold_keys for c, p in
                      zip(df["case"], df["para_seq"])], index=df.index)
    pool = df[~excl]
    print(f"  pool {len(pool)} of {len(df)} (excluded {int(excl.sum())} gold few-shots)")
    sample = pool.sample(n=N, random_state=SEED)
    print("  surface composition:", sample["surface_meaning"].value_counts().to_dict())
    write_workbook(sample, ["case", "para_num", "para_seq"],
                   ROOT / "modified_data" / "Legal IRR Round 3 RANDOM N100.xlsx",
                   ROOT / "code" / "dev" / "_irr_round3_random_manifest_legal.csv")


def draw_media() -> None:
    print("MEDIA Round 3 RANDOM draw")
    df = pd.read_excel(ROOT / "modified_data" / "media_paragraphs.xlsx")
    gold = pd.read_excel(ROOT / "modified_data" / "media_fewshot_gold100.xlsx")
    gold_keys = set(zip(gold["document_id"], gold["para_idx"]))
    excl = pd.Series([(d, p) in gold_keys for d, p in
                      zip(df["document_id"], df["para_idx"])], index=df.index)
    pool = df[df["article_usable"] & ~df["is_duplicate"] & ~excl]
    print(f"  pool {len(pool)} of {len(df)} (excluded {int(excl.sum())} gold few-shots; "
          f"rest non-usable/duplicate)")
    sample = pool.sample(n=N, random_state=SEED)
    write_workbook(sample, ["document_id", "para_idx"],
                   ROOT / "modified_data" / "Media IRR Round 3 RANDOM N100.xlsx",
                   ROOT / "code" / "dev" / "_irr_round3_random_manifest_media.csv")


if __name__ == "__main__":
    draw_legal()
    draw_media()
