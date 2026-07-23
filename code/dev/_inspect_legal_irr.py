"""Inspect LLM's codings against the 30-row legal IRR sample."""
import pandas as pd

irr = pd.read_excel("Addiction v Attachment Legal Corpus IRR.xlsx", sheet_name="IRR")
llm = pd.read_excel("legal_paragraphs_llm.xlsx")

irr["_k"] = list(zip(irr.case.astype(str), irr.para_num))
llm["_k"] = list(zip(llm.case.astype(str), llm.para_num))
merged = irr.merge(
    llm[["_k", "deeper_meaning", "reasoning"]].drop_duplicates(subset="_k"),
    on="_k", how="left"
)

def norm(s): return str(s).strip().lower()

print("="*120)
print(f"{'#':>2} {'case':<22} {'¶':>4} {'Jul':<11} {'Ita':<11} {'Omk':<11} {'CONS':<11} {'LLM':<11} agree?")
print("="*120)
for i, r in merged.iterrows():
    cons = norm(r["final_code"])
    llmc = norm(r["deeper_meaning"])
    agree = "✓" if cons == llmc else "✗"
    print(f"{i+1:>2} {str(r['case'])[:22]:<22} {int(r['para_num']):>4} "
          f"{str(r['code_julian'])[:11]:<11} {str(r['code_itai'])[:11]:<11} "
          f"{str(r['code_omkar'])[:11]:<11} {str(r['final_code'])[:11]:<11} "
          f"{str(r['deeper_meaning'])[:11]:<11} {agree}")

print()
print("="*120)
print("DISAGREEMENTS (consensus ≠ LLM):")
print("="*120)
for i, r in merged.iterrows():
    cons = norm(r["final_code"])
    llmc = norm(r["deeper_meaning"])
    if cons != llmc:
        print(f"\n--- #{i+1}: {r['case']} ¶{int(r['para_num'])} ---")
        print(f"   Humans: Julian={r['code_julian']} | Itai={r['code_itai']} | Omkar={r['code_omkar']}")
        print(f"   Consensus: {r['final_code']} (justification: {str(r['justification_final'])[:200]})")
        print(f"   LLM:       {r['deeper_meaning']}")
        print(f"   LLM reasoning: {str(r['reasoning'])[:280]}")
        print(f"   Paragraph: {str(r['para_text'])[:280]}...")
