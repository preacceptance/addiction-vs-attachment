#!/usr/bin/env python3
"""Split the reconciled Legal IRR N=100 gold set into 50 few-shot / 50 held-out IRR.

Stratified by (final_code, llm_v5_correct) so each half mirrors both the gold
label distribution and the current LLM-v5 error mix — a random split within
those cells, seeded for reproducibility.

Outputs:
  modified_data/legal_fewshot_gold50.xlsx   (few-shot half, fewshot_v3 column format)
  code/dev/_irr_gold50_manifest_legal.csv   (held-out IRR half, with gold + LLM codes)
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEED = 20260610

cons = pd.read_excel(ROOT / "modified_data" / "Legal IRR Round 2 N100 coded.xlsx",
                     sheet_name="Consensus")
spliced = pd.read_excel(ROOT / "output" / "legal_irr_v5_spliced.xlsx")

df = cons.merge(spliced[["case", "para_num", "llm_v4", "llm_v5"]],
                on=["case", "para_num"], how="left")
assert len(df) == 100 and df["llm_v5"].notna().all()

for col in ["final_code", "llm_v5"]:
    df[col] = df[col].astype(str).str.strip().str.lower()
df["v5_correct"] = df["final_code"] == df["llm_v5"]

# stratified half-split within each (final_code, v5_correct) cell;
# odd cells alternate their extra row between halves so totals land 50/50
fewshot_idx = []
odd_to_fewshot = True
for _, cell in df.groupby(["final_code", "v5_correct"]):
    take = len(cell) // 2
    if len(cell) % 2:
        take += odd_to_fewshot
        odd_to_fewshot = not odd_to_fewshot
    fewshot_idx += list(cell.sample(n=take, random_state=SEED).index)

few = df.loc[sorted(fewshot_idx)]
held = df.drop(index=fewshot_idx).sort_index()
assert len(few) + len(held) == 100
assert not set(zip(few["case"], few["para_num"])) & set(zip(held["case"], held["para_num"]))

fewshot_out = few.rename(columns={"final_code": "code",
                                  "justification_final": "justification"})
fewshot_out["stratum"] = few["final_code"]
fewshot_out = fewshot_out[["case", "para_num", "para_seq", "stratum", "para_text", "code", "justification"]]
fewshot_out.to_excel(ROOT / "modified_data" / "legal_fewshot_gold50.xlsx", index=False)

held_out = held[["case", "para_num", "para_seq", "para_text",
                 "code_itai", "code_omkar", "final_code", "llm_v4", "llm_v5"]]
held_out.to_csv(ROOT / "code" / "dev" / "_irr_gold50_manifest_legal.csv", index=False)

print(f"few-shot half ({len(few)}):", few["final_code"].value_counts().to_dict(),
      "| v5 errors:", int((~few["v5_correct"]).sum()))
print(f"held-out half ({len(held)}):", held["final_code"].value_counts().to_dict(),
      "| v5 errors:", int((~held["v5_correct"]).sum()))
