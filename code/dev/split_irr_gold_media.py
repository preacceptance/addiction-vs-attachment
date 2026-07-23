#!/usr/bin/env python3
"""Split the reconciled Media IRR N=100 gold set into 50 few-shot / 50 held-out.

Mirror of split_irr_gold.py (legal). Stratified by (final_code, llm_v4_correct)
— no media v5 codes exist, so the v4 manifests provide the error-mix dimension.
Keys on (document_id, para_idx).

Outputs:
  modified_data/media_fewshot_gold50.xlsx   (few-shot half, media fewshot column format)
  code/dev/_irr_gold50_manifest_media.csv   (held-out half with gold + v4 LLM codes)
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEED = 20260610

cons = pd.read_excel(ROOT / "modified_data" / "Media IRR Round 2 N100 coded.xlsx",
                     sheet_name="Consensus")
v4 = pd.concat([
    pd.read_csv(ROOT / "code" / "dev" / "_round2_manifest_media.csv"),
    pd.read_csv(ROOT / "code" / "dev" / "_round2_supplement_manifest_media.csv"),
]).rename(columns={"deeper_meaning": "llm_v4"})

df = cons.merge(v4, on=["document_id", "para_idx"], how="left")
assert len(df) == 100 and df["llm_v4"].notna().all(), "v4 manifest merge incomplete"

for col in ["final_code", "llm_v4"]:
    df[col] = df[col].astype(str).str.strip().str.lower()
assert df["final_code"].isin(["addiction", "attachment", "both", "neither"]).all()
df["v4_correct"] = df["final_code"] == df["llm_v4"]

# stratified half-split within each (final_code, v4_correct) cell;
# odd cells alternate their extra row between halves so totals land 50/50
fewshot_idx = []
odd_to_fewshot = True
for _, cell in df.groupby(["final_code", "v4_correct"]):
    take = len(cell) // 2
    if len(cell) % 2:
        take += odd_to_fewshot
        odd_to_fewshot = not odd_to_fewshot
    fewshot_idx += list(cell.sample(n=take, random_state=SEED).index)

few = df.loc[sorted(fewshot_idx)]
held = df.drop(index=fewshot_idx).sort_index()
assert len(few) + len(held) == 100
assert not (set(zip(few["document_id"], few["para_idx"]))
            & set(zip(held["document_id"], held["para_idx"])))

fewshot_out = few.rename(columns={"final_code": "code",
                                  "justification_final": "justification"})
fewshot_out["stratum"] = few["final_code"]
fewshot_out = fewshot_out[["document_id", "para_idx", "stratum",
                           "para_text", "code", "justification"]]
fewshot_out.to_excel(ROOT / "modified_data" / "media_fewshot_gold50.xlsx", index=False)

held_out = held[["document_id", "para_idx", "para_text",
                 "code_itai", "code_omkar", "final_code", "llm_v4"]]
held_out.to_csv(ROOT / "code" / "dev" / "_irr_gold50_manifest_media.csv", index=False)

print(f"few-shot half ({len(few)}):", few["final_code"].value_counts().to_dict(),
      "| v4 errors:", int((~few["v4_correct"]).sum()),
      "| justifications missing:", int(fewshot_out["justification"].isna().sum()))
print(f"held-out half ({len(held)}):", held["final_code"].value_counts().to_dict(),
      "| v4 errors:", int((~held["v4_correct"]).sum()))
