#!/usr/bin/env python3
"""
Round 2 SUPPLEMENT — adds 50 paragraphs per corpus on top of the existing
Round 2 N=50, so the final IRR sample is N=100 stratified 25/25/25/25 across
LLM-predicted deeper_meaning (addiction / attachment / both / neither).

Supplement targets (12/12/13/13) top up the existing R2 (13/13/12/12) to
exactly 25 per category. Single coder (Omkar + co-authors in a Google Sheet
that mirrors the BLANK).

Exclusions for this draw:
  - few-shot (legal_fewshot_v3.xlsx / media_fewshot_v3.xlsx)
  - current Round 2 N=50 (Legal/Media IRR Round 2 N50 BLANK.xlsx)
  - Round 1 IRR (N=30) is INTENTIONALLY NOT excluded — write-off per user.

Outputs:
  modified_data/Legal IRR Round 2 N50 SUPPLEMENT BLANK.xlsx
  modified_data/Media IRR Round 2 N50 SUPPLEMENT BLANK.xlsx
  code/dev/_round2_supplement_manifest_legal.csv
  code/dev/_round2_supplement_manifest_media.csv
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "modified_data"
OUT  = ROOT / "output"
DEV  = Path(__file__).resolve().parent

RANDOM_STATE = 2027   # R2 used 2026; R1 used 42/99
# Top-up so final R2+supplement = 25/25/25/25 if all strata have enough.
# If a stratum is exhausted, the shortfall is redistributed evenly across
# the other strata so the supplement still totals N=50.
TARGETS = {"addiction": 12, "attachment": 12, "both": 13, "neither": 13}
SUPPLEMENT_TOTAL = sum(TARGETS.values())  # 50


def stratified_sample_with_redistribution(
    pool: pd.DataFrame, targets: dict[str, int], total: int,
) -> pd.DataFrame:
    """Stratified sample. If any stratum has fewer rows than its target, take
    all available and redistribute the shortfall across the other strata
    (in priority order: neither > attachment > addiction > both) so the
    overall N still hits `total`."""
    priority = ["neither", "attachment", "addiction", "both"]
    taken = {}
    shortfall = 0
    for code, n in targets.items():
        n_avail = len(pool[pool["deeper_meaning"].str.lower() == code])
        if n_avail < n:
            print(f"  NOTE: '{code}' exhausted at {n_avail} (target {n}); "
                  f"redistributing {n - n_avail} slot(s) to other strata")
            shortfall += (n - n_avail)
            taken[code] = n_avail
        else:
            taken[code] = n

    # Distribute shortfall round-robin across strata that still have headroom
    i = 0
    safety = 0
    while shortfall > 0 and safety < 1000:
        code = priority[i % len(priority)]
        n_avail = len(pool[pool["deeper_meaning"].str.lower() == code])
        if taken.get(code, 0) < n_avail:
            taken[code] += 1
            shortfall -= 1
        i += 1
        safety += 1

    parts = []
    for code, n in taken.items():
        if n == 0:
            continue
        stratum = pool[pool["deeper_meaning"].str.lower() == code]
        parts.append(stratum.sample(n=n, random_state=RANDOM_STATE))
    out = pd.concat(parts).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    assert len(out) == total or shortfall > 0, f"got {len(out)}, expected {total}"
    return out


# ── LEGAL ──────────────────────────────────────────────────────────────────
print("LEGAL")
llm    = pd.read_excel(OUT  / "legal_paragraphs_llm.xlsx")
fewsh  = pd.read_excel(DATA / "legal_fewshot_v3.xlsx")
r2     = pd.read_excel(DATA / "Legal IRR Round 2 N50 BLANK.xlsx")

exclude_keys = (
    set(zip(fewsh["case"].astype(str), fewsh["para_num"].astype(int))) |
    set(zip(r2["case"].astype(str),    r2["para_num"].astype(int)))
)
print(f"  exclude: {len(exclude_keys)} rows (fewshot + R2 N50)")

pool = llm[~llm.apply(lambda r: (str(r["case"]), int(r["para_num"])) in exclude_keys, axis=1)].copy()
print(f"  pool size: {len(pool)} (of {len(llm)} total)")
print(f"  pool deeper_meaning counts:\n{pool['deeper_meaning'].value_counts().to_string()}")

legal_supp = stratified_sample_with_redistribution(pool, TARGETS, SUPPLEMENT_TOTAL)
print(f"  sampled n={len(legal_supp)}")
print(f"  sample deeper_meaning counts:\n{legal_supp['deeper_meaning'].value_counts().to_string()}")

legal_blank = legal_supp[["case", "para_num", "para_seq", "para_text"]].copy()
legal_blank["code_omkar"]          = ""
legal_blank["justification_omkar"] = ""
legal_blank.to_excel(DATA / "Legal IRR Round 2 N50 SUPPLEMENT BLANK.xlsx", index=False)
print(f"  wrote {DATA / 'Legal IRR Round 2 N50 SUPPLEMENT BLANK.xlsx'}")

legal_supp[["case", "para_num", "para_seq", "deeper_meaning"]].to_csv(
    DEV / "_round2_supplement_manifest_legal.csv", index=False)
print(f"  wrote {DEV / '_round2_supplement_manifest_legal.csv'}")


# ── MEDIA ──────────────────────────────────────────────────────────────────
print("\nMEDIA")
mllm    = pd.read_excel(OUT  / "media_paragraphs_llm.xlsx")
mfewsh  = pd.read_excel(DATA / "media_fewshot_v3.xlsx")
mr2     = pd.read_excel(DATA / "Media IRR Round 2 N50 BLANK.xlsx")

mllm = mllm[mllm["article_usable"] & ~mllm["is_duplicate"]].copy()
mllm = mllm[mllm["deeper_meaning"].astype(str).str.strip() != ""].copy()
print(f"  full unique-usable coded pool: {len(mllm)}")

mexclude_keys = (
    set(zip(mfewsh["document_id"].astype(str), mfewsh["para_idx"].astype(int))) |
    set(zip(mr2["document_id"].astype(str),    mr2["para_idx"].astype(int)))
)
print(f"  exclude: {len(mexclude_keys)} rows (fewshot + R2 N50)")

mpool = mllm[~mllm.apply(lambda r: (str(r["document_id"]), int(r["para_idx"])) in mexclude_keys, axis=1)].copy()
print(f"  pool size: {len(mpool)}")
print(f"  pool deeper_meaning counts:\n{mpool['deeper_meaning'].value_counts().to_string()}")

media_supp = stratified_sample_with_redistribution(mpool, TARGETS, SUPPLEMENT_TOTAL)
print(f"  sampled n={len(media_supp)}")
print(f"  sample deeper_meaning counts:\n{media_supp['deeper_meaning'].value_counts().to_string()}")

media_blank = media_supp[["document_id", "para_idx", "para_text"]].copy()
media_blank["code_omkar"]          = ""
media_blank["justification_omkar"] = ""
media_blank.to_excel(DATA / "Media IRR Round 2 N50 SUPPLEMENT BLANK.xlsx", index=False)
print(f"  wrote {DATA / 'Media IRR Round 2 N50 SUPPLEMENT BLANK.xlsx'}")

media_supp[["document_id", "para_idx", "deeper_meaning"]].to_csv(
    DEV / "_round2_supplement_manifest_media.csv", index=False)
print(f"  wrote {DEV / '_round2_supplement_manifest_media.csv'}")
