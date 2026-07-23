#!/usr/bin/env python3
"""v7 IRR draw — STRATIFIED by v7 LLM deeper_meaning, N=150 per corpus.

Design (2026-07-08): the IRR set is stratified by the v7 LLM code (canonical
pass-2 output) so agreement isn't a Neither-class artifact and the κ tests the
actual attachment↔neither boundary. Allocation is DERIVED, not hard-coded (see
allocate()): split 150 evenly across the four classes, cap any class at its
availability, redistribute the shortfall across the rest. On the v7+A/B pool
(2026-07-08) this yields legal 49 add / 49 att / 48 nei / 4 both (avail
68/247/3677/4) and media 42 add / 42 att / 41 nei / 25 both (avail
138/1081/19920/25) — the only class that caps is 'both' in both corpora.
Change the pool and the numbers recompute themselves; nothing to hand-edit.
NOTE: legal 'both' has only 4 rows → per-cell κ unstable; report raw
agreement alongside.

Exclusion: ONLY the v7 few-shots (is_fewshot). They are the prompt answer
keys and carry the human gold code, NOT an LLM code, so scoring on them is
circular. No other exclusions — clean slate (prior v5-era sets are dissolved
into the corpus; coders can't recall specific rows under a different manual).

Balanced (not prevalence-weighted) → report raw agreement alongside κ.

Outputs per corpus (only with --write):
  modified_data/{Legal,Media} IRR v7 STRATIFIED N150.xlsx  (blind Itai + Omkar)
  code/dev/_irr_v7_stratified_manifest_{legal,media}.csv   (keys + para_text; NO LLM codes)

Blind sheets/manifest carry NO LLM codes — coders code blind; the stratum/LLM
code lives only in the production output and is recovered at scoring time by
joining on keys (preserves the κ chain).

Usage:  python3 draw_irr_stratified.py           # dry-run: print realized strata
        python3 draw_irr_stratified.py --write    # generate the sheets
Seed 20260708. Verified 2026-07-09: shipped sheets/manifests reproduce
byte-identically from this seed; 150/150 join to production; 0 few-shot
overlap; blind sheets carry no codes and are row-aligned across raters.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEED = 20260708
N = 150
CLASSES = ["addiction", "attachment", "both", "neither"]
WRITE = "--write" in sys.argv


def allocate(avail: dict[str, int], n: int) -> dict[str, int]:
    """Split n as evenly as possible across the classes, capped at each class's
    availability, with the shortfall from capped classes redistributed equally
    across the rest (water-filling). Deterministic; sums to min(n, total avail).
    This is the PRINCIPLE — no hard-coded per-class numbers — so it stays valid
    if the pool changes (on the v7 pool, 'both' caps in both corpora).
    """
    alloc, remaining, active = {}, n, set(avail)
    while active:
        share = remaining / len(active)
        capped = [c for c in active if avail[c] < share]
        if not capped:
            break
        for c in capped:
            alloc[c] = avail[c]
            remaining -= avail[c]
            active.discard(c)
    act = sorted(active)  # sorted → deterministic assignment of the leftover +1s
    if act:
        base, extra = divmod(remaining, len(act))
        for i, c in enumerate(act):
            alloc[c] = base + (1 if i < extra else 0)
    return alloc


def stratified(pool: pd.DataFrame, target: dict[str, int]) -> pd.DataFrame:
    parts = []
    for cls, n in target.items():
        g = pool[pool["deeper_meaning"] == cls]
        take = min(n, len(g))
        if take < n:
            print(f"    NOTE: '{cls}' short — wanted {n}, took all {take}")
        parts.append(g.sample(n=take, random_state=SEED))
    return pd.concat(parts).sample(frac=1, random_state=SEED).reset_index(drop=True)


def write_workbook(sample: pd.DataFrame, id_cols: list[str],
                   out_xlsx: Path, manifest_csv: Path) -> None:
    blank = sample[id_cols + ["para_text"]].reset_index(drop=True)
    with pd.ExcelWriter(out_xlsx) as xw:
        for rater in ["Itai", "Omkar"]:
            sheet = blank.copy()
            sheet[f"code_{rater.lower()}"] = ""
            sheet[f"justification_{rater.lower()}"] = ""
            sheet.to_excel(xw, sheet_name=rater, index=False)
    blank.to_csv(manifest_csv, index=False)
    print(f"  wrote {out_xlsx.name} + {manifest_csv.name}  (n={len(blank)})")


def draw(corpus: str, llm_path: Path, id_cols: list[str], usable_filter: bool) -> None:
    print(f"{corpus.upper()} IRR v7 stratified draw")
    df = pd.read_excel(llm_path)
    if usable_filter:
        df = df[df["article_usable"] & ~df["is_duplicate"]]
    df["deeper_meaning"] = df["deeper_meaning"].astype(str).str.strip()
    pool = df[~df["is_fewshot"] & (df["deeper_meaning"] != "")]
    print(f"  pool {len(pool)} (excluded {int(df['is_fewshot'].sum())} v7 few-shots)")

    avail = {c: int((pool["deeper_meaning"] == c).sum()) for c in CLASSES}
    target = allocate(avail, N)
    print(f"  available per class: {avail}")
    print(f"  target (derived, sum {sum(target.values())}): {target}")
    sample = stratified(pool, target)
    print(f"  realized strata: {sample['deeper_meaning'].value_counts().to_dict()}  total {len(sample)}")

    if WRITE:
        write_workbook(sample, id_cols,
                       ROOT / "modified_data" / f"{corpus.capitalize()} IRR v7 STRATIFIED N150.xlsx",
                       ROOT / "code" / "dev" / f"_irr_v7_stratified_manifest_{corpus}.csv")
    else:
        print("  [dry-run] no files written — re-run with --write to generate sheets")
    print()


if __name__ == "__main__":
    draw("legal", ROOT / "output" / "legal_paragraphs_llm.xlsx",
         ["case", "para_num", "para_seq"], usable_filter=False)
    draw("media", ROOT / "output" / "media_paragraphs_llm.xlsx",
         ["document_id", "para_idx"], usable_filter=True)
    print("done." + ("  (WROTE sheets)" if WRITE else "  (dry-run)"))
