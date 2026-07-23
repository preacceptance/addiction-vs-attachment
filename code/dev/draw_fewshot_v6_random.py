#!/usr/bin/env python3
"""v6 few-shot draw — RANDOM N=150 per corpus (design locked 2026-06-17).

Per the 2026-06-17 design: few-shot exemplars are a SIMPLE RANDOM SAMPLE
(prevalence-realistic, no circularity — drawn before any v6 LLM pass), in
contrast to the IRR set, which is stratified by v6 LLM code and drawn later.
Random few-shots keep the exemplar class mix at true prevalence, which should
dampen (not feed) the persistent Neither->substantive over-coding.

Pool & exclusions:
  Legal: all 4,146 paragraphs.
  Media: unique-usable pool (article_usable & ~is_duplicate), 21,314 paragraphs.
  Both: EXCLUDE every paragraph previously double-coded by the team —
        the old gold-100 few-shots and the Round-3 RANDOM IRR-100 — so coders
        see fresh text and this set is disjoint from all prior rounds.
        (The new stratified IRR set, drawn later, will in turn exclude THESE.)

Outputs per corpus:
  modified_data/{Legal,Media} Few-shot v6 RANDOM N150.xlsx
      sheets Itai + Omkar: id cols + para_text + blank code_/justification_ cols
      (NO LLM codes — coders work blind; they will be coded under the v6 manual)
  code/dev/_fewshot_v6_random_manifest_{legal,media}.csv
      id cols + para_text only (keys for later joins)

Seed 20260617. N=150. Coders see only para_text (same unit the LLM sees).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEED = 20260617
N = 150


def _prior_keys(files_keys: list[tuple[Path, list[str]]]) -> set[tuple]:
    """Collect (key-tuple) sets from prior coded files/manifests."""
    keys: set[tuple] = set()
    for path, cols in files_keys:
        if not path.exists():
            print(f"    NOTE: prior set not found, skipping: {path.name}")
            continue
        df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
        keys |= set(zip(*(df[c] for c in cols)))
        print(f"    excluding {len(df)} from {path.name}")
    return keys


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
    print(f"  wrote {out_xlsx.name} + {manifest_csv.name}  (n={len(blank)})")


def draw_legal() -> None:
    print("LEGAL few-shot v6 RANDOM draw")
    df = pd.read_excel(ROOT / "modified_data" / "legal_paragraphs.xlsx")
    prior = _prior_keys([
        (ROOT / "modified_data" / "legal_fewshot_gold100.xlsx", ["case", "para_seq"]),
        (ROOT / "code" / "dev" / "_irr_round3_random_manifest_legal.csv", ["case", "para_seq"]),
    ])
    excl = pd.Series([(c, p) in prior for c, p in zip(df["case"], df["para_seq"])],
                     index=df.index)
    pool = df[~excl]
    print(f"  pool {len(pool)} of {len(df)} (excluded {int(excl.sum())} prior-coded)")
    sample = pool.sample(n=N, random_state=SEED)
    print("  surface composition:", sample["surface_meaning"].value_counts().to_dict())
    write_workbook(sample, ["case", "para_num", "para_seq"],
                   ROOT / "modified_data" / "Legal Few-shot v6 RANDOM N150.xlsx",
                   ROOT / "code" / "dev" / "_fewshot_v6_random_manifest_legal.csv")


def draw_media() -> None:
    print("MEDIA few-shot v6 RANDOM draw")
    df = pd.read_excel(ROOT / "modified_data" / "media_paragraphs.xlsx")
    prior = _prior_keys([
        (ROOT / "modified_data" / "media_fewshot_gold100.xlsx", ["document_id", "para_idx"]),
        (ROOT / "code" / "dev" / "_irr_round3_random_manifest_media.csv", ["document_id", "para_idx"]),
    ])
    base = df[df["article_usable"] & ~df["is_duplicate"]]
    excl = pd.Series([(d, p) in prior for d, p in zip(base["document_id"], base["para_idx"])],
                     index=base.index)
    pool = base[~excl]
    print(f"  pool {len(pool)} of {len(base)} unique-usable (excluded {int(excl.sum())} prior-coded)")
    sample = pool.sample(n=N, random_state=SEED)
    print("  surface composition:", sample["surface_meaning"].value_counts().to_dict())
    write_workbook(sample, ["document_id", "para_idx"],
                   ROOT / "modified_data" / "Media Few-shot v6 RANDOM N150.xlsx",
                   ROOT / "code" / "dev" / "_fewshot_v6_random_manifest_media.csv")


if __name__ == "__main__":
    draw_legal()
    draw_media()
    print("done.")
