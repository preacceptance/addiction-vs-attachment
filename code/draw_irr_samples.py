#!/usr/bin/env python3
"""
Reproduce the two N=150 reliability (IRR) samples reported in the paper.

One sample per corpus (legal complaints, media articles). Each sample is a
stratified draw of 150 paragraphs from the LLM-coded production output of that
corpus, made with a fixed random seed. This script re-runs both draws and
asserts that the resulting 150 unit_ids — in the exact shuffled order — match
the sample manifests shipped with the project (`_manifest_legal_irr24_v9.xlsx`
and `_manifest_media_irr24.xlsx`).

Design of each draw (identical for both corpora):
  * Pool = all coded paragraphs, excluding the few-shot exemplar paragraphs
    (their answers were written by the human coders, so they cannot be used
    to validate the coders against the model).
  * Stratification is BALANCED over the four production codes (addiction,
    attachment, both, neither): every stratum aims for 150/4 rows. A stratum
    with fewer available rows than its aim contributes everything it has, and
    the shortfall is split evenly across the remaining strata. Because the
    strata are balanced rather than prevalence-weighted, raw agreement is
    always reported alongside kappa.
  * The 150 selected rows are shuffled so that the coding sheet's row order
    carries no stratum information.

Corpus-specific details:
  * LEGAL is drawn from the current production pass
    (2_coding/legal_paragraphs_24_llm_v9p2.xlsx), fixed seed 20260812.
    The `both` stratum has fewer rows than its aim and is exhausted.
  * MEDIA is drawn from an earlier production pass of the same pipeline
    (2_coding/media_paragraphs_24_llm_p2.xlsx); the seed and stratification
    used then are preserved here. The historical draw script seeded a base
    generator at 20260808 and gave the media draw its own random stream
    offset by one, so the media generator seed is 20260808 + 1. Media is
    drawn over UNIQUE TEXTS (one representative unit per normalized text):
    a syndicated copy is the same paragraph, and spending two of 150 human
    judgments on identical text measures nothing. Paragraphs whose text
    matches a few-shot exemplar are excluded along with the exemplars.

Fallback mode: if a corpus's stratification source workbook is not present
(the media source contains licensed article text and may not ship), the
script cannot re-run that draw. It then VERIFIES the shipped manifest
instead: 150 rows, unique unit_ids, every unit_id present in the coded
corpus workbook, and the per-stratum counts recorded in the manifest are
printed. The full re-draw + assert is the primary mode.

This script only reads files; it writes nothing.

Usage:  python3 draw_irr_samples.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CODING = HERE.parent / "output"
DATA = HERE.parent / "modified_data"

# ---- inputs (all paths relative to this file's folder) ----------------------
# Stratification sources: the LLM production outputs each draw was made from.
LEGAL_SOURCE = CODING / "legal_paragraphs_24_llm_v9p2.xlsx"
MEDIA_SOURCE = CODING / "media_paragraphs_24_llm_p2.xlsx"

# Sample manifests: the shipped record of each drawn sample (row order fixed).
LEGAL_MANIFEST = DATA / "_manifest_legal_irr24_v9.xlsx"
MEDIA_MANIFEST = DATA / "_manifest_media_irr24.xlsx"

# Coded corpus workbooks, used only by the fallback verification mode.
LEGAL_CORPUS = DATA / "legal_CODED_paragraphs_24.xlsx"
MEDIA_CORPUS = DATA / "media_CODED_paragraphs_24.xlsx"

# Fixed seeds (see module docstring for the media offset).
LEGAL_SEED = 20260812
MEDIA_SEED = 20260808 + 1

N = 150
CATS = ["addiction", "attachment", "both", "neither"]


def allocate(avail: dict[str, int], n: int) -> dict[str, int]:
    """Balanced allocation of n draws over strata, with shortfall
    redistribution: a stratum smaller than an equal share contributes all its
    rows, and the deficit is split evenly across the remaining strata.
    Reproduced exactly from the original draw scripts, including iteration
    order, because the order of the returned dict fixes the order in which
    the random generator is consumed."""
    take = {}
    cells = dict(avail)
    remaining = n
    # exhaust strata that cannot meet an equal share, smallest first
    while cells:
        share = remaining // len(cells)
        short = {c: k for c, k in cells.items() if k <= share}
        if not short:
            break
        for c, k in short.items():
            take[c] = k
            remaining -= k
            del cells[c]
    order = sorted(cells)          # deterministic remainder assignment
    share, extra = divmod(remaining, len(cells)) if cells else (0, 0)
    for i, c in enumerate(order):
        take[c] = share + (1 if i < extra else 0)
    assert sum(take.values()) == n, take
    return take


def stratified_draw(pool: pd.DataFrame, seed: int) -> pd.DataFrame:
    """The draw itself, byte-for-byte the same procedure as the original
    scripts: one seeded generator per corpus; one child seed per stratum, in
    the allocation dict's order; one final child seed for the shuffle."""
    rng = np.random.default_rng(seed)
    avail = pool["deeper_meaning"].value_counts().to_dict()
    take = allocate(avail, N)
    print(f"  pool {len(pool):,} rows; drawing {take}")
    picks = [pool[pool["deeper_meaning"] == cat]
             .sample(n=k, random_state=rng.integers(0, 2**31))
             for cat, k in take.items()]
    sample = pd.concat(picks)
    # shuffle so the coding-sheet order carries no stratum information
    sample = sample.sample(frac=1, random_state=rng.integers(0, 2**31)).reset_index(drop=True)
    return sample


def assert_matches_manifest(sample: pd.DataFrame, manifest_path: Path,
                            corpus: str) -> None:
    """The re-drawn sample must equal the shipped manifest exactly:
    same 150 unit_ids, in the same (shuffled) order, same strata."""
    manifest = pd.read_excel(manifest_path)
    got = list(sample["unit_id"])
    want = list(manifest["unit_id"])
    assert len(got) == N and len(want) == N, (len(got), len(want))
    if got != want:
        first = next(i for i, (g, w) in enumerate(zip(got, want)) if g != w)
        raise AssertionError(
            f"{corpus}: re-draw does not match {manifest_path.name}. "
            f"First difference at row {first + 1}: drew {got[first]!r}, "
            f"manifest has {want[first]!r}. "
            f"Set difference (drawn - manifest): {sorted(set(got) - set(want))[:5]}")
    strata = list(sample["deeper_meaning"])
    assert strata == list(manifest["deeper_meaning"]), \
        f"{corpus}: unit_ids match but stratum labels differ"
    print(f"  SUCCESS ({corpus}): re-draw reproduces {manifest_path.name} "
          f"exactly — all {N} unit_ids in order, strata "
          f"{manifest['deeper_meaning'].value_counts().to_dict()}")


def verify_against_manifest(manifest_path: Path, corpus_path: Path,
                            corpus: str) -> None:
    """Fallback when the stratification source workbook is unavailable:
    check the shipped manifest against the coded corpus workbook instead of
    re-running the draw."""
    print(f"  NOTE ({corpus}): stratification source not found; falling back "
          f"to verifying the shipped manifest against the coded corpus.")
    manifest = pd.read_excel(manifest_path)
    assert len(manifest) == N, f"{corpus}: manifest has {len(manifest)} rows, expected {N}"
    assert manifest["unit_id"].is_unique, f"{corpus}: duplicate unit_ids in manifest"
    corpus_df = pd.read_excel(corpus_path)
    if "unit_id" not in corpus_df.columns:
        # the media corpus workbook stores the id's components separately;
        # a unit's id is "<pdf>#u<unit_seq>"
        corpus_df["unit_id"] = (corpus_df["pdf"].astype(str) + "#u"
                                + corpus_df["unit_seq"].astype(str))
    corpus_ids = set(corpus_df["unit_id"])
    missing = [u for u in manifest["unit_id"] if u not in corpus_ids]
    assert not missing, f"{corpus}: manifest unit_ids absent from corpus: {missing[:5]}"
    strata = manifest["deeper_meaning"].value_counts().to_dict()
    assert sum(strata.values()) == N and set(strata) <= set(CATS), strata
    print(f"  SUCCESS ({corpus}, verify mode): all {N} manifest unit_ids are "
          f"unique and present in {corpus_path.name}; recorded strata {strata}")


def run_legal() -> None:
    print("LEGAL")
    if not LEGAL_SOURCE.exists():
        verify_against_manifest(LEGAL_MANIFEST, LEGAL_CORPUS, "legal")
        return
    df = pd.read_excel(LEGAL_SOURCE)
    pool = df[~df["is_fewshot"] & df["deeper_meaning"].isin(CATS)].copy()
    sample = stratified_draw(pool, LEGAL_SEED)
    assert_matches_manifest(sample, LEGAL_MANIFEST, "legal")


def run_media() -> None:
    print("MEDIA")
    if not MEDIA_SOURCE.exists():
        verify_against_manifest(MEDIA_MANIFEST, MEDIA_CORPUS, "media")
        return
    df = pd.read_excel(MEDIA_SOURCE)
    # exclude few-shot exemplars and any syndicated copies of their text,
    # then keep one representative row per unique normalized text
    df = df[~df["is_fewshot"] & ~df["is_fewshot_dup"]]
    df = df.drop_duplicates("text_key")
    pool = df[df["deeper_meaning"].isin(CATS)].copy()
    sample = stratified_draw(pool, MEDIA_SEED)
    assert_matches_manifest(sample, MEDIA_MANIFEST, "media")


def main() -> None:
    run_legal()
    run_media()


if __name__ == "__main__":
    main()
