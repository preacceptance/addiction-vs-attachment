#!/usr/bin/env python3
"""Few-shot ablation on the held-out gold 50 under the v5-Bowlby manual.

Arms (manual fixed at Coding_Instructions_v5_Bowlby.docx):
  v3        — original 30 v3 few-shots
  gold50    — 50 gold few-shots, justifications now complete
  combined  — v3 + gold50 (80 exemplars)

Each arm codes only the 50 held-out rows (~50 calls). Reports gold-vs-LLM
kappa per arm alongside the v5 baseline (0.762 on these rows).
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from openai import OpenAI
from sklearn.metrics import cohen_kappa_score
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "dev"))

import llm_pass_v2 as L  # type: ignore
from run_v5bowlby_fullpass import build_system_prompt  # type: ignore

L.load_dotenv()

ARMS = {
    "v3":       ROOT / "modified_data" / "legal_fewshot_v3.xlsx",
    "gold50":   ROOT / "modified_data" / "legal_fewshot_gold50.xlsx",
    "combined": ROOT / "modified_data" / "legal_fewshot_v3_plus_gold50.xlsx",
}
OUT = ROOT / "output" / "fewshot_ablation_heldout50.xlsx"


def main() -> None:
    L.LEGAL_CODING_SYSTEM = build_system_prompt()
    man = pd.read_csv(ROOT / "code" / "dev" / "_irr_gold50_manifest_legal.csv")
    for col in ["final_code", "llm_v4", "llm_v5"]:
        man[col] = man[col].astype(str).str.strip().str.lower()
    client = OpenAI()

    for arm, fs_file in ARMS.items():
        L.FEW_SHOT_FILE = fs_file
        fewshot = L.build_fewshot_messages()

        def task(i):
            comp = L.code_paragraph(client, str(man.at[i, "para_text"]), fewshot)
            return i, comp.deeper_meaning if comp else None

        with ThreadPoolExecutor(max_workers=L.CONCURRENT_WORKERS) as ex:
            futs = [ex.submit(task, i) for i in man.index]
            for fut in tqdm(as_completed(futs), total=len(futs), desc=arm):
                i, code = fut.result()
                man.at[i, f"llm_{arm}"] = code

    man.to_excel(OUT, index=False)
    print(f"\nSaved {OUT}\n")
    print("=== gold-vs-LLM kappa on held-out 50, v5-Bowlby manual ===")
    print(f"baseline v5 manual + v3 fewshots : {cohen_kappa_score(man['final_code'], man['llm_v5']):.3f}")
    for arm in ARMS:
        col = f"llm_{arm}"
        ok = man[man[col].notna()]
        k = cohen_kappa_score(ok["final_code"], ok[col])
        raw = (ok["final_code"] == ok[col]).mean()
        print(f"bowlby + {arm:<24}: {k:.3f}  raw={raw:.2f}  (n={len(ok)})")
    for arm in ARMS:
        print(f"\nconfusion, bowlby + {arm}:")
        print(pd.crosstab(man["final_code"], man[f"llm_{arm}"]))


if __name__ == "__main__":
    main()
