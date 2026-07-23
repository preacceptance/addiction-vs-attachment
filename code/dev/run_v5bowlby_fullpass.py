#!/usr/bin/env python3
"""Full legal-corpus LLM pass under the v5-Bowlby manual + 50 gold few-shots.

Arm: Bowlby-explicit manual (Coding_Instructions_v5_Bowlby.docx, read verbatim
at runtime) + gold few-shots (legal_fewshot_gold50.xlsx, reconciled consensus).

- Codes all 4,146 legal paragraphs EXCEPT the 50 gold few-shot rows (4,096 sent
  to the LLM). Few-shot rows are written to the output with their gold
  final_code and flagged is_fewshot=True so corpus totals stay 4,146.
- After the pass, scores IRR on the 50 held-out gold rows
  (_irr_gold50_manifest_legal.csv): per-rater kappa, gold-vs-LLM kappa, Fleiss.

Output: output/legal_paragraphs_llm_v5bowlby.xlsx
        output/irr_gold50_v5bowlby_scores.txt
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from openai import OpenAI
from sklearn.metrics import cohen_kappa_score
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "code"))

import llm_pass_v2 as L  # type: ignore

L.load_dotenv()

MANUAL_DOCX  = ROOT / "Coding_Instructions_v5_Bowlby.docx"
FEWSHOT_FILE = ROOT / "modified_data" / "legal_fewshot_gold50.xlsx"
MANIFEST     = ROOT / "code" / "dev" / "_irr_gold50_manifest_legal.csv"
OUTPUT       = ROOT / "output" / "legal_paragraphs_llm_v5bowlby.xlsx"
SCORES_TXT   = ROOT / "output" / "irr_gold50_v5bowlby_scores.txt"
CHECKPOINT   = ROOT / "output" / "_v5bowlby_checkpoint.csv"

OUTPUT_BLOCK = '''

OUTPUT
  deeper_meaning: one of "addiction", "attachment", "both", "neither"
  reasoning: one sentence justifying the code
  reasoning: one sentence justifying the code'''


def build_system_prompt() -> str:
    doc = Document(MANUAL_DOCX)
    body = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return body + OUTPUT_BLOCK


def fleiss_kappa(codes: pd.DataFrame) -> float:
    """Fleiss kappa for rows x raters of categorical codes."""
    cats = sorted(set(codes.values.ravel()))
    counts = np.array([[(row == c).sum() for c in cats] for _, row in codes.iterrows()])
    n = counts.sum(axis=1)[0]
    p_i = ((counts ** 2).sum(axis=1) - n) / (n * (n - 1))
    p_bar = p_i.mean()
    p_e = ((counts.sum(axis=0) / counts.sum()) ** 2).sum()
    return (p_bar - p_e) / (1 - p_e)


def main() -> None:
    # swap in the Bowlby manual and gold few-shots
    L.LEGAL_CODING_SYSTEM = build_system_prompt()
    L.FEW_SHOT_FILE = FEWSHOT_FILE
    fewshot = L.build_fewshot_messages()
    assert len(fewshot) == 100, f"expected 50 exemplar pairs, got {len(fewshot) // 2}"

    df = pd.read_excel(ROOT / "modified_data" / "legal_paragraphs.xlsx")
    gold_fs = pd.read_excel(FEWSHOT_FILE)
    # key on (case, para_seq) — para_num restarts within cases and collides
    fs_keys = set(zip(gold_fs["case"], gold_fs["para_seq"]))
    fs_codes = {(r["case"], r["para_seq"]): r["code"] for _, r in gold_fs.iterrows()}

    df["deeper_meaning"] = ""
    df["reasoning"] = ""
    df["is_fewshot"] = [
        (c, p) in fs_keys for c, p in zip(df["case"], df["para_seq"])]

    assert df["is_fewshot"].sum() == 50, "few-shot keys did not all match corpus"

    # resume from checkpoint: rows coded in a previous (interrupted) run are reused
    done: dict[tuple, dict] = {}
    if CHECKPOINT.exists():
        ck = pd.read_csv(CHECKPOINT)
        done = {(r["case"], r["para_seq"]): r for _, r in ck.iterrows()}
        print(f"Checkpoint: {len(done)} rows already coded, skipping them")
    for idx in df.index[~df["is_fewshot"]]:
        prev = done.get((df.at[idx, "case"], df.at[idx, "para_seq"]))
        if prev is not None:
            df.at[idx, "deeper_meaning"] = prev["deeper_meaning"]
            df.at[idx, "reasoning"] = prev["reasoning"]

    to_code = df.index[~df["is_fewshot"] & (df["deeper_meaning"] == "")].tolist()
    print(f"Coding {len(to_code)} paragraphs ({df['is_fewshot'].sum()} gold few-shots excluded)")

    client = OpenAI()
    ck_file = open(CHECKPOINT, "a")
    if not done:
        ck_file.write("case,para_seq,deeper_meaning,reasoning\n")
    import csv as _csv
    import threading
    ck_writer = _csv.writer(ck_file)
    ck_lock = threading.Lock()

    def task(idx):
        comp = L.code_paragraph(client, str(df.at[idx, "para_text"]), fewshot)
        return idx, comp

    with ThreadPoolExecutor(max_workers=L.CONCURRENT_WORKERS) as ex:
        futs = [ex.submit(task, i) for i in to_code]
        for fut in tqdm(as_completed(futs), total=len(futs), desc="LEGAL v5-Bowlby"):
            idx, comp = fut.result()
            if comp:
                df.at[idx, "deeper_meaning"] = comp.deeper_meaning
                df.at[idx, "reasoning"] = comp.reasoning
                with ck_lock:
                    ck_writer.writerow([df.at[idx, "case"], df.at[idx, "para_seq"],
                                        comp.deeper_meaning, comp.reasoning])
                    ck_file.flush()
    ck_file.close()

    # few-shot rows carry their gold code, clearly flagged
    for idx in df.index[df["is_fewshot"]]:
        df.at[idx, "deeper_meaning"] = fs_codes[(df.at[idx, "case"], df.at[idx, "para_seq"])]
        df.at[idx, "reasoning"] = "GOLD FEW-SHOT — human consensus code, not LLM-coded"

    df.to_excel(OUTPUT, index=False)
    failed = (df["deeper_meaning"] == "").sum()
    print(f"Wrote {OUTPUT}  ({len(df)} rows, {failed} failed calls)")

    lines = [f"=== v5-Bowlby full pass ({len(to_code)} LLM-coded) ==="]
    llm_only = df[~df["is_fewshot"] & (df["deeper_meaning"] != "")]
    lines.append("LLM-coded distribution: " + str(llm_only["deeper_meaning"].value_counts().to_dict()))
    resid = llm_only[llm_only["surface_meaning"] == "neither"]
    att, add = (resid["deeper_meaning"] == "attachment").sum(), (resid["deeper_meaning"] == "addiction").sum()
    lines.append(f"Residual (no-vocab): {att} attachment vs {add} addiction → {att / max(add, 1):.1f}x")

    # ── IRR on the 50 held-out gold rows ──
    man = pd.read_csv(MANIFEST)
    m = man.merge(df[["case", "para_seq", "deeper_meaning"]], on=["case", "para_seq"], how="left")
    m = m.rename(columns={"deeper_meaning": "llm_v5b"})
    for col in ["code_itai", "code_omkar", "final_code", "llm_v4", "llm_v5", "llm_v5b"]:
        m[col] = m[col].astype(str).str.strip().str.lower()
    ok = m[m["llm_v5b"].isin(["addiction", "attachment", "both", "neither"])]
    lines.append(f"\n=== IRR, held-out gold 50 (n={len(ok)}) ===")
    for name, col in [("Itai  vs LLM-v5b", "code_itai"), ("Omkar vs LLM-v5b", "code_omkar"),
                      ("GOLD  vs LLM-v5b", "final_code")]:
        k = cohen_kappa_score(ok[col], ok["llm_v5b"])
        raw = (ok[col] == ok["llm_v5b"]).mean()
        lines.append(f"{name}: kappa={k:.3f}  raw={raw:.2f}")
    for name, col in [("GOLD vs LLM-v4 (same 50)", "llm_v4"), ("GOLD vs LLM-v5 (same 50)", "llm_v5")]:
        lines.append(f"{name}: kappa={cohen_kappa_score(ok['final_code'], ok[col]):.3f}")
    lines.append(f"Fleiss (Itai+Omkar+LLM-v5b): {fleiss_kappa(ok[['code_itai', 'code_omkar', 'llm_v5b']]):.3f}")
    lines.append("\nGOLD vs LLM-v5b confusion:")
    lines.append(str(pd.crosstab(ok["final_code"], ok["llm_v5b"])))

    report = "\n".join(lines)
    print(report)
    SCORES_TXT.write_text(report)
    print(f"\nSaved {SCORES_TXT}")


if __name__ == "__main__":
    main()
