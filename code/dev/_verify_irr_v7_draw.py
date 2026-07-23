#!/usr/bin/env python3
"""Verify the v7 stratified IRR draw is correct before sharing.

Checks per corpus:
 1. Manifest joins 150/150 to canonical production output on keys
 2. Realized strata (via join) match the documented counts
 3. Zero overlap with the v7 few-shots (by keys, and by is_fewshot flag)
 4. Manifest / sheets carry NO code columns; Itai & Omkar sheets row-aligned
   and identical to the manifest (ids + text), code/justification blank
 5. No duplicate keys inside the sample
 6. Media sample is entirely unique-usable
 7. Reproducibility: re-derive the sample from seed 20260708 with the same
    logic and compare key-sets to the shipped manifest
 8. allocate() re-derivation matches realized strata
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/ojoshi/Desktop/Ethical Intelligence Lab/addiction-vs-attachment")
SEED = 20260708
N = 150
CLASSES = ["addiction", "attachment", "both", "neither"]

sys.path.insert(0, str(ROOT / "code" / "dev"))
from draw_irr_stratified import allocate, stratified  # reuse the real logic

FAILS = []
def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(f"{name}: {detail}")

def verify(corpus, llm_path, id_cols, usable_filter, fewshot_path, fs_id_cols, expected_strata):
    print(f"\n=== {corpus.upper()} ===")
    prod = pd.read_excel(llm_path)
    manifest = pd.read_csv(ROOT / "code" / "dev" / f"_irr_v7_stratified_manifest_{corpus}.csv")
    xlsx = ROOT / "modified_data" / f"{corpus.capitalize()} IRR v7 STRATIFIED N150.xlsx"
    itai = pd.read_excel(xlsx, sheet_name="Itai")
    omkar = pd.read_excel(xlsx, sheet_name="Omkar")

    # 1. join manifest -> production
    prod_u = prod[prod["article_usable"] & ~prod["is_duplicate"]] if usable_filter else prod
    dup_prod = prod_u.duplicated(subset=id_cols).sum()
    check("production keys unique", dup_prod == 0, f"{dup_prod} dup keys in production")
    j = manifest.merge(prod_u[id_cols + ["deeper_meaning", "is_fewshot", "para_text"]],
                       on=id_cols, how="left", suffixes=("", "_prod"))
    check("manifest N=150", len(manifest) == 150, f"n={len(manifest)}")
    check("150/150 join to production", j["deeper_meaning"].notna().all(),
          f"{j['deeper_meaning'].isna().sum()} unmatched")
    check("manifest text == production text",
          (j["para_text"].astype(str) == j["para_text_prod"].astype(str)).all())

    # 2. realized strata
    realized = j["deeper_meaning"].value_counts().to_dict()
    check("realized strata match documented", realized == expected_strata,
          f"realized {realized} vs expected {expected_strata}")

    # 3. few-shot overlap
    check("no is_fewshot rows in sample", not j["is_fewshot"].any(),
          f"{int(j['is_fewshot'].sum())} few-shot rows")
    fs = pd.read_excel(fewshot_path)
    fs_keys = set(map(tuple, fs[fs_id_cols].astype(str).values))
    m_keys = set(map(tuple, manifest[[c for c in id_cols if c in fs_id_cols or True]][fs_id_cols].astype(str).values)) if set(fs_id_cols) <= set(manifest.columns) else None
    if m_keys is not None:
        overlap = fs_keys & m_keys
        check("zero overlap with few-shot file (by keys)", len(overlap) == 0, f"{len(overlap)} overlapping")
    else:
        check("few-shot key columns present in manifest", False, f"fs cols {fs_id_cols} vs manifest {list(manifest.columns)}")

    # 4. blind sheets
    for name, sheet in [("Itai", itai), ("Omkar", omkar)]:
        expected_cols = id_cols + ["para_text", f"code_{name.lower()}", f"justification_{name.lower()}"]
        check(f"{name} sheet columns exact", list(sheet.columns) == expected_cols, f"{list(sheet.columns)}")
        code_blank = sheet[f"code_{name.lower()}"].isna().all() or (sheet[f"code_{name.lower()}"].astype(str).str.strip() == "").all()
        just_blank = sheet[f"justification_{name.lower()}"].isna().all() or (sheet[f"justification_{name.lower()}"].astype(str).str.strip() == "").all()
        check(f"{name} code+justification blank", code_blank and just_blank)
        aligned = (sheet[id_cols].astype(str).values == manifest[id_cols].astype(str).values).all() and \
                  (sheet["para_text"].astype(str).values == manifest["para_text"].astype(str).values).all()
        check(f"{name} sheet row-aligned with manifest", bool(aligned))
    no_llm_cols = not any(c in manifest.columns for c in ["deeper_meaning", "reasoning", "surface", "code"])
    check("manifest carries no LLM/code columns", no_llm_cols, f"{list(manifest.columns)}")

    # 5. duplicates within sample
    dups = manifest.duplicated(subset=id_cols).sum()
    check("no duplicate keys in sample", dups == 0, f"{dups} dups")

    # 6. media usable
    if usable_filter:
        j2 = manifest.merge(prod[id_cols + ["article_usable", "is_duplicate"]].drop_duplicates(id_cols), on=id_cols, how="left")
        check("all rows unique-usable", bool((j2["article_usable"] & ~j2["is_duplicate"]).all()))

    # 7. reproducibility from seed
    df = prod.copy()
    if usable_filter:
        df = df[df["article_usable"] & ~df["is_duplicate"]]
    df["deeper_meaning"] = df["deeper_meaning"].astype(str).str.strip()
    pool = df[~df["is_fewshot"] & (df["deeper_meaning"] != "")]
    avail = {c: int((pool["deeper_meaning"] == c).sum()) for c in CLASSES}
    target = allocate(avail, N)
    redraw = stratified(pool, target)
    rk = set(map(tuple, redraw[id_cols].astype(str).values))
    mk = set(map(tuple, manifest[id_cols].astype(str).values))
    check("re-draw from seed reproduces shipped keys", rk == mk,
          f"only-in-redraw {len(rk - mk)}, only-in-shipped {len(mk - rk)}")
    order_ok = (redraw[id_cols].astype(str).values == manifest[id_cols].astype(str).values).all()
    check("re-draw row ORDER matches shipped", bool(order_ok))

    # 8. allocation re-derivation
    check("allocate(avail,150) == realized", target == {k: expected_strata.get(k, 0) for k in target},
          f"target {target}  avail {avail}")
    print(f"  pool size {len(pool)}, few-shots excluded {int(df['is_fewshot'].sum())}, avail {avail}")

verify("legal", ROOT / "output" / "legal_paragraphs_llm.xlsx",
       ["case", "para_num", "para_seq"], False,
       ROOT / "modified_data" / "legal_fewshot_v7.xlsx", ["case", "para_seq"],
       {"addiction": 49, "attachment": 49, "neither": 48, "both": 4})

verify("media", ROOT / "output" / "media_paragraphs_llm.xlsx",
       ["document_id", "para_idx"], True,
       ROOT / "modified_data" / "media_fewshot_v7.xlsx", ["document_id", "para_idx"],
       {"addiction": 42, "attachment": 42, "neither": 41, "both": 25})

print("\n" + ("ALL CHECKS PASSED" if not FAILS else f"{len(FAILS)} FAILURES:\n" + "\n".join(" - " + f for f in FAILS)))
