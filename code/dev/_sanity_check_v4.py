"""Run the 30 legal IRR paragraphs through the v4 prompt and compare to consensus."""
import pandas as pd
from sklearn.metrics import cohen_kappa_score
from openai import OpenAI
from llm_pass_v2 import build_fewshot_messages, code_paragraph, LEGAL_CODING_SYSTEM

CLIENT = OpenAI()

irr = pd.read_excel("Addiction v Attachment Legal Corpus IRR.xlsx", sheet_name="IRR")
fewshot = build_fewshot_messages()

results = []
for i, row in irr.iterrows():
    text = str(row["para_text"])
    comp = code_paragraph(CLIENT, text, fewshot)
    llm_code = comp.deeper_meaning.strip().lower() if comp else "error"
    results.append({
        "case":        row["case"],
        "para_num":    row["para_num"],
        "consensus":   str(row["final_code"]).strip().lower(),
        "llm_v4":      llm_code,
        "reasoning":   comp.reasoning if comp else "",
    })
    print(f"  {i+1:>2}  {str(row['case'])[:22]:<22} ¶{int(row['para_num']):>4}  "
          f"cons={str(row['final_code'])[:10]:<10}  llm={llm_code:<10}  "
          f"{'✓' if str(row['final_code']).strip().lower() == llm_code else '✗'}")

df = pd.DataFrame(results)
agree = (df["consensus"] == df["llm_v4"]).mean()
try:
    kappa = cohen_kappa_score(df["consensus"], df["llm_v4"],
                              labels=["addiction","attachment","both","neither"])
except Exception as e:
    kappa = float("nan")
    print(f"kappa error: {e}")

print(f"\n{'='*60}")
print(f"Agreement: {agree:.1%}  ({int(agree*30)}/30)")
print(f"Cohen kappa (consensus vs LLM v4): {kappa:+.3f}")
print(f"\nDisagreements:")
for _, r in df[df["consensus"] != df["llm_v4"]].iterrows():
    print(f"  {r['case']} ¶{int(r['para_num'])}  cons={r['consensus']}  llm={r['llm_v4']}")
    print(f"    {r['reasoning'][:180]}")
