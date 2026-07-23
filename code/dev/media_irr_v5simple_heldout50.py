#!/usr/bin/env python3
"""Media held-out gold 50 under the production config:
v5-simplified manual (now baked in llm_pass_v2.LEGAL_CODING_SYSTEM) +
media gold-50 few-shots (media_fewshot_gold50.xlsx).

Reports per-rater, gold-vs-LLM, and Fleiss kappa, with the v4 baseline
(gold vs the original v4 codes) on the same 50 rows.

Output: output/media_irr_v5simple_heldout50.xlsx + printed report.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from openai import OpenAI
from sklearn.metrics import cohen_kappa_score
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "code"))

import llm_pass_v2 as L  # type: ignore

L.load_dotenv()

OUT = ROOT / "output" / "media_irr_v5simple_heldout50.xlsx"


def fleiss_kappa(codes: pd.DataFrame) -> float:
    cats = sorted(set(codes.values.ravel()))
    counts = np.array([[(row == c).sum() for c in cats] for _, row in codes.iterrows()])
    n = counts.sum(axis=1)[0]
    p_i = ((counts ** 2).sum(axis=1) - n) / (n * (n - 1))
    p_e = ((counts.sum(axis=0) / counts.sum()) ** 2).sum()
    return (p_i.mean() - p_e) / (1 - p_e)


def main() -> None:
    # production manual is already LEGAL_CODING_SYSTEM; only the few-shot file
    # is corpus-specific (media gold-50, same columns the legal builder expects)
    L.FEW_SHOT_FILE = ROOT / "modified_data" / "media_fewshot_gold50.xlsx"
    fewshot = L.build_fewshot_messages()
    assert len(fewshot) == 100

    man = pd.read_csv(ROOT / "code" / "dev" / "_irr_gold50_manifest_media.csv")
    for col in ["code_itai", "code_omkar", "final_code", "llm_v4"]:
        man[col] = man[col].astype(str).str.strip().str.lower()
    client = OpenAI()

    def task(i):
        comp = L.code_paragraph(client, str(man.at[i, "para_text"]), fewshot)
        return i, comp.deeper_meaning if comp else None

    with ThreadPoolExecutor(max_workers=L.CONCURRENT_WORKERS) as ex:
        futs = [ex.submit(task, i) for i in man.index]
        for fut in tqdm(as_completed(futs), total=len(futs), desc="media held-out 50"):
            i, code = fut.result()
            man.at[i, "llm_v5simple"] = code

    man.to_excel(OUT, index=False)
    ok = man[man["llm_v5simple"].notna()]
    print(f"\nSaved {OUT}")
    print(f"\n=== MEDIA held-out gold 50 (n={len(ok)}), v5-simplified + gold-50 few-shots ===")
    for name, col in [("Itai  vs LLM", "code_itai"), ("Omkar vs LLM", "code_omkar"),
                      ("GOLD  vs LLM", "final_code")]:
        k = cohen_kappa_score(ok[col], ok["llm_v5simple"])
        raw = (ok[col] == ok["llm_v5simple"]).mean()
        print(f"{name}: kappa={k:.3f}  raw={raw:.2f}")
    print(f"GOLD vs LLM-v4 baseline (same 50): "
          f"kappa={cohen_kappa_score(ok['final_code'], ok['llm_v4']):.3f}")
    print(f"Itai vs Omkar (blind, same 50): "
          f"kappa={cohen_kappa_score(ok['code_itai'], ok['code_omkar']):.3f}")
    print(f"Fleiss (Itai+Omkar+LLM): "
          f"{fleiss_kappa(ok[['code_itai', 'code_omkar', 'llm_v5simple']]):.3f}")
    print("\nGOLD vs LLM confusion:")
    print(pd.crosstab(ok["final_code"], ok["llm_v5simple"]))


if __name__ == "__main__":
    main()
