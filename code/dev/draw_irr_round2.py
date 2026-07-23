#!/usr/bin/env python3
"""
Round 2 IRR sampler — stratified N=50 per corpus.

For each corpus, draw 50 paragraphs stratified by LLM-predicted deeper_meaning
(13/13/12/12 across addiction/attachment/both/neither), disjoint from the
Round 1 IRR sample and the few-shot calibration set.

Outputs:
  modified_data/Legal IRR Round 2 N50 BLANK.xlsx   (blank code column for Omkar)
  modified_data/Media IRR Round 2 N50 BLANK.xlsx   (same)
  code/dev/_round2_manifest_legal.csv              (hidden: LLM code per row)
  code/dev/_round2_manifest_media.csv              (hidden: LLM code per row)

Stratification key: deeper_meaning (LLM-assigned). Coders see only para_text
and a blank `code` cell. After coding, compute_irr_round2.py joins on the
identifier columns and reports κ.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "modified_data"
OUT  = ROOT / "output"
DEV  = Path(__file__).resolve().parent

RANDOM_STATE = 2026
TARGETS = {"addiction": 13, "attachment": 13, "both": 12, "neither": 12}


def stratified_sample(pool: pd.DataFrame, targets: dict[str, int]) -> pd.DataFrame:
    """Stratified random sample by deeper_meaning; degrades gracefully if a
    stratum is smaller than its target (takes all available)."""
    parts = []
    for code, n in targets.items():
        stratum = pool[pool["deeper_meaning"].str.lower() == code]
        n_avail = len(stratum)
        if n_avail < n:
            print(f"  WARNING: only {n_avail} rows available for '{code}' "
                  f"(target {n}) — taking all of them")
        parts.append(stratum.sample(n=min(n, n_avail), random_state=RANDOM_STATE))
    return pd.concat(parts).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)


# ── LEGAL ──────────────────────────────────────────────────────────────────
print("LEGAL")
llm    = pd.read_excel(OUT  / "legal_paragraphs_llm.xlsx")
fewsh  = pd.read_excel(DATA / "legal_fewshot_v3.xlsx")
irr_r1 = pd.read_excel(DATA / "Addiction v Attachment Legal Corpus IRR.xlsx", sheet_name="IRR")

exclude_keys = set(zip(fewsh["case"].astype(str), fewsh["para_num"].astype(int))) | \
               set(zip(irr_r1["case"].astype(str), irr_r1["para_num"].astype(int)))
print(f"  exclude: {len(exclude_keys)} rows (fewshot + R1 IRR)")

pool = llm[~llm.apply(lambda r: (str(r["case"]), int(r["para_num"])) in exclude_keys, axis=1)].copy()
print(f"  pool size: {len(pool)} (of {len(llm)} total)")
print(f"  pool deeper_meaning counts:\n{pool['deeper_meaning'].value_counts().to_string()}")

legal_sample = stratified_sample(pool, TARGETS)
print(f"  sampled n={len(legal_sample)}")
print(f"  sample deeper_meaning counts:\n{legal_sample['deeper_meaning'].value_counts().to_string()}")

# Blank coding sheet (no LLM code visible)
legal_blank = legal_sample[["case", "para_num", "para_seq", "para_text"]].copy()
legal_blank["code_omkar"]          = ""
legal_blank["justification_omkar"] = ""
legal_blank.to_excel(DATA / "Legal IRR Round 2 N50 BLANK.xlsx", index=False)
print(f"  wrote {DATA / 'Legal IRR Round 2 N50 BLANK.xlsx'}")

# Hidden manifest (LLM code per row, for later κ computation)
legal_sample[["case", "para_num", "para_seq", "deeper_meaning"]].to_csv(
    DEV / "_round2_manifest_legal.csv", index=False)
print(f"  wrote {DEV / '_round2_manifest_legal.csv'}")


# ── MEDIA ──────────────────────────────────────────────────────────────────
print("\nMEDIA")
mllm   = pd.read_excel(OUT  / "media_paragraphs_llm.xlsx")
mfewsh = pd.read_excel(DATA / "media_fewshot_v3.xlsx")
mirr_r1 = pd.read_excel(DATA / "Addiction vs Attachment Media corpus IRR.xlsx", sheet_name="IRR")

# Restrict to unique-usable analysis pool
mllm = mllm[mllm["article_usable"] & ~mllm["is_duplicate"]].copy()
mllm = mllm[mllm["deeper_meaning"].astype(str).str.strip() != ""].copy()
print(f"  full unique-usable coded pool: {len(mllm)}")

mexclude_keys = set(zip(mfewsh["document_id"].astype(str), mfewsh["para_idx"].astype(int))) | \
                set(zip(mirr_r1["document_id"].astype(str), mirr_r1["para_idx"].astype(int)))
print(f"  exclude: {len(mexclude_keys)} rows (fewshot + R1 IRR)")

mpool = mllm[~mllm.apply(lambda r: (str(r["document_id"]), int(r["para_idx"])) in mexclude_keys, axis=1)].copy()
print(f"  pool size: {len(mpool)}")
print(f"  pool deeper_meaning counts:\n{mpool['deeper_meaning'].value_counts().to_string()}")

media_sample = stratified_sample(mpool, TARGETS)
print(f"  sampled n={len(media_sample)}")
print(f"  sample deeper_meaning counts:\n{media_sample['deeper_meaning'].value_counts().to_string()}")

media_blank = media_sample[["document_id", "para_idx", "para_text"]].copy()
media_blank["code_omkar"]          = ""
media_blank["justification_omkar"] = ""
media_blank.to_excel(DATA / "Media IRR Round 2 N50 BLANK.xlsx", index=False)
print(f"  wrote {DATA / 'Media IRR Round 2 N50 BLANK.xlsx'}")

media_sample[["document_id", "para_idx", "deeper_meaning"]].to_csv(
    DEV / "_round2_manifest_media.csv", index=False)
print(f"  wrote {DEV / '_round2_manifest_media.csv'}")
