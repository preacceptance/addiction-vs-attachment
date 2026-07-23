"""Compute IRR for both corpora from the final IRR files (2026-05-30).

Reports three blocks per corpus:
  1. PRE-CONSENSUS pairwise + Fleiss kappa among the 3 human coders
  2. PRE-CONSENSUS pairwise kappa of each human vs the LLM, plus Fleiss 4-rater
  3. POST-CONSENSUS kappa of the adjudicated `final_code` vs the LLM

REPORTING CONVENTION FOR THE MANUSCRIPT
---------------------------------------
Report TWO kappa values in the paper, NOT the 4-rater Fleiss:

  * Human IRR  = Fleiss kappa on the 3 humans only
                 -> measures inter-rater reliability of the coding scheme
  * LLM validity = kappa vs the post-consensus `final_code`
                 -> measures how well the LLM matches human-validated truth

The 4-rater Fleiss conflates these two questions because the LLM is being
validated against the humans, not treated as an exchangeable peer rater.
It is fine in supplementary materials but should not be the headline.

Suggested methods sentence:
  "Inter-rater reliability among the 3 expert coders was Fleiss kappa =
   0.899 (legal) / 0.826 (media), indicating almost perfect agreement.
   After adjudication of disagreements to produce a consensus code,
   agreement between the LLM and the human consensus was kappa =
   0.642 (legal) / 0.947 (media)."
"""
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.metrics import cohen_kappa_score
from statsmodels.stats.inter_rater import fleiss_kappa

ROOT      = Path(__file__).resolve().parent.parent
LEGAL_IRR = ROOT / "modified_data" / "Addiction v Attachment Legal Corpus IRR.xlsx"
LEGAL_LLM = ROOT / "output" / "legal_paragraphs_llm.xlsx"
MEDIA_IRR = ROOT / "modified_data" / "Addiction vs Attachment Media corpus IRR.xlsx"
MEDIA_LLM = ROOT / "output" / "media_paragraphs_llm.xlsx"

CATS = ["addiction", "attachment", "both", "neither"]


def norm(s):
    return str(s).strip().lower()


def fleiss_from(arr):
    M = np.zeros((arr.shape[0], len(CATS)), int)
    for i, row in enumerate(arr):
        for v in row:
            v = norm(v)
            if v in CATS:
                M[i, CATS.index(v)] += 1
    return fleiss_kappa(M)


def report(name, df, h_cols, llm_col=None, consensus_col=None):
    print(f"===== {name} =====")
    rows = df.dropna(subset=h_cols)
    print(f"N (3-human rows): {len(rows)}")
    j, i, o = (rows[c].map(norm) for c in h_cols)
    print("  --- PRE-CONSENSUS (raw human codes) ---")
    print(f"    Julian-Itai  kappa = {cohen_kappa_score(j, i):+.3f}")
    print(f"    Julian-Omkar kappa = {cohen_kappa_score(j, o):+.3f}")
    print(f"    Itai-Omkar   kappa = {cohen_kappa_score(i, o):+.3f}")
    print(f"    Fleiss 3-human kappa = {fleiss_from(rows[h_cols].values):+.3f}")
    if llm_col is not None:
        coded = rows.dropna(subset=[llm_col])
        coded = coded[coded[llm_col].astype(str).str.strip() != ""]
        print(f"    LLM-matched: {len(coded)}/{len(rows)}")
        if len(coded):
            llm_c = coded[llm_col].map(norm)
            j2, i2, o2 = (coded[c].map(norm) for c in h_cols)
            print(f"    Julian-LLM kappa = {cohen_kappa_score(j2, llm_c):+.3f}")
            print(f"    Itai-LLM   kappa = {cohen_kappa_score(i2, llm_c):+.3f}")
            print(f"    Omkar-LLM  kappa = {cohen_kappa_score(o2, llm_c):+.3f}")
            four = coded[h_cols + [llm_col]].values
            print(f"    Fleiss 4-rater kappa (3 humans + LLM) = {fleiss_from(four):+.3f}")
    if consensus_col is not None and llm_col is not None:
        sub = rows.dropna(subset=[consensus_col, llm_col])
        sub = sub[(sub[consensus_col].astype(str).str.strip() != "") &
                  (sub[llm_col].astype(str).str.strip() != "")]
        print("  --- POST-CONSENSUS (final adjudicated code vs LLM) ---")
        print(f"    Rows: {len(sub)}/{len(rows)}")
        if len(sub):
            cons_c = sub[consensus_col].map(norm)
            llm_c = sub[llm_col].map(norm)
            agree = (cons_c == llm_c).mean()
            print(f"    Consensus-LLM kappa = {cohen_kappa_score(cons_c, llm_c):+.3f}   agree = {agree:.1%}")
    print()


# Legal
li = pd.read_excel(LEGAL_IRR, sheet_name="IRR")
li = li[["case", "para_num", "code_julian", "code_itai", "code_omkar", "final_code"]].copy()
llm = pd.read_excel(LEGAL_LLM)
li["_k"] = list(zip(li.case.astype(str), li.para_num))
llm["_k"] = list(zip(llm.case.astype(str), llm.para_num))
li = li.merge(
    llm[["_k", "deeper_meaning"]].drop_duplicates(subset="_k"),
    on="_k",
    how="left",
)
report("LEGAL", li, ["code_julian", "code_itai", "code_omkar"], "deeper_meaning", "final_code")

# Media
mi = pd.read_excel(MEDIA_IRR, sheet_name="IRR")
mi = mi[["document_id", "para_idx", "code_julian", "code_itai", "code_omkar", "final_code"]].copy()
mllm = pd.read_excel(MEDIA_LLM)
mi["_k"] = list(zip(mi.document_id.astype(str), mi.para_idx))
mllm["_k"] = list(zip(mllm.document_id.astype(str), mllm.para_idx))
mi = mi.merge(
    mllm[["_k", "deeper_meaning"]].drop_duplicates(subset="_k"),
    on="_k",
    how="left",
)
report("MEDIA", mi, ["code_julian", "code_itai", "code_omkar"], "deeper_meaning", "final_code")
