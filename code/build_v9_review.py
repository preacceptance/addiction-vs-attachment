"""
Score the revised-instruction (v9) pass-2 LLM codes against the frozen blind
human consensus, and build a review page for the residual disagreements: each
is flagged NEW (agreed under the previous instruction version, disagrees now)
or CARRIED (disagreed under both versions), with an editable notes column that
autosaves through save_server.py. Rows resolved by the revision are listed in
the page header.

Inputs: the coded IRR consensus workbook, the previous scoring run
(irr24_<corpus>_scored.xlsx), and 2_coding/<corpus>_paragraphs_24_llm_v9p2.xlsx.
Outputs: irr24_<corpus>_scored_v9.xlsx and <corpus>_disagreements_v9.html.

Usage:  python3 build_v9_review.py [legal|media]
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from build_disagreement_html import CLAUDE, CODE_COLORS  # comments carried from the previous review round

HERE = Path(__file__).resolve().parent
CODING = HERE.parent / "output"
DATA = HERE.parent / "modified_data"
OUT = HERE.parent / "output"
CODES = ["addiction", "attachment", "both", "neither"]

NEW_COMMENTS = {
    ("legal", 1): "The model now reads 'attempt to go offline failed miserably' as being about his suicide attempt, not about quitting ChatGPT, so it dropped impaired control. Genuinely ambiguous sentence. Keep addiction or accept Neither, either is defensible.",
    ("legal", 14): "Your new delusion rule working exactly as written: mom-can't-understand-him inside the Timelord delusion no longer counts. Keeping attachment here means Irwin gets a different rule than Soelberg. Flip to Neither for consistency, or tell me what makes Irwin different.",
    ("legal", 61): "Identical paragraph to row 144. v9 says the word 'Grooming' in a category list isn't defining vocabulary, so addiction only. You ruled 144 stays Both. Decide once for both copies: flip these two to addiction, or we add a grooming-counts-in-lists line to the manual and re-run (the cache makes that cheap).",
    ("legal", 102): "The 'keep him hooked' plus kept-talking-instead-of-calling-help paragraph, twin of row 62 which now agrees. v9 dropped the attachment half, reading 'false sense of connection' as a design phrase. Flip to addiction if you agree the connection half is a label.",
    ("legal", 129): "Same as row 14, the other Irwin delusion row. Your rule now excludes it. Flip to Neither for consistency or keep and accept the Irwin/Soelberg split.",
    ("legal", 141): "Half a win: you fixed this to Both, and v9 now agrees on the attachment half (preference for AI companions over humans) but dropped 'withdrawal', reading it as social withdrawal inside a harms list under the new tolerance clause. If you think clinical withdrawal is genuinely stated, keep Both; otherwise flip to attachment.",
}

CSS = """
:root{--line:#e2e2df;--ink:#1e1e1c;--soft:#6b6b66;}
*{box-sizing:border-box}
body{font:14px/1.5 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif;color:var(--ink);margin:0;background:#faf9f6}
header{padding:16px 24px 8px}
h1{font-size:19px;margin:0 0 4px}
.sub{color:var(--soft);font-size:13px;margin:0;max-width:1100px}
.toolbar{display:flex;gap:8px;align-items:center;padding:10px 24px 12px;flex-wrap:wrap}
button{font:inherit;font-size:12.5px;padding:5px 10px;border:1px solid #bbb;border-radius:6px;background:#fff;cursor:pointer}
button.on{background:#2f2f2b;color:#fff;border-color:#2f2f2b}
#savenote{font-size:12px;display:flex;align-items:center;gap:6px}
#dot{width:9px;height:9px;border-radius:50%;background:#bbb;display:inline-block}
#dot.disk{background:#2e9e44}
.wrap{overflow-x:auto;padding:0 24px 40px}
table{border-collapse:collapse;width:100%;min-width:1600px;background:#fff;border:1px solid var(--line)}
th{position:sticky;top:0;background:#2f2f2b;color:#fff;text-align:left;padding:8px 10px;font-size:12.5px;z-index:2}
td{border-top:1px solid var(--line);padding:9px 10px;vertical-align:top;font-size:13px}
.codechip{font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:9px;color:#fff;display:inline-block;margin:1px 0}
.st{font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:9px;color:#fff;display:inline-block;margin-bottom:5px}
.st.new{background:#b3541e}
.st.carried{background:#6b6b66}
.c-code{width:140px}
.c-para{width:24%;max-width:400px;white-space:pre-wrap}
.c-rater{width:11%;background:#fbf7ef}
.c-llm{width:16%;background:#f7f2f9}
.c-claude{width:17%}
.c-resp{width:13%;min-width:170px;background:#f2f7ff;outline:none;white-space:pre-wrap}
.c-resp:focus{background:#e8f1ff;box-shadow:inset 0 0 0 2px #7aa7e8}
.c-resp:empty::before{content:"flip? keep? note here…";color:#9aa4b0}
.meta{color:var(--soft);font-size:11.5px;margin-top:5px}
.just{margin-top:4px}
.empty{color:#b0aca2;font-style:italic}
details summary{cursor:pointer;color:#444}
.hl{font-weight:600;font-size:12.5px;margin-bottom:4px}
"""

JS = """
let dirty = {};
function filt(p){
  document.querySelectorAll('.toolbar button[data-f]').forEach(b=>b.classList.toggle('on',b.dataset.f===p));
  document.querySelectorAll('tbody tr').forEach(tr=>{tr.style.display=(p==='all'||tr.dataset.st===p)?'':'none';});
}
function save(){
  const keys=Object.keys(dirty); if(!keys.length) return;
  const payload={r3:{}};
  keys.forEach(k=>{payload.r3[k]=document.querySelector(`[data-key="${k}"]`).innerHTML;});
  fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(r=>{if(r.ok){dirty={};document.getElementById('dot').className='disk';
      document.getElementById('savetext').textContent='saved '+new Date().toLocaleTimeString();}})
    .catch(()=>{document.getElementById('savetext').textContent='server not running — python3 save_server.py';});
}
document.addEventListener('input',e=>{
  if(!e.target.dataset.key) return;
  dirty[e.target.dataset.key]=1;
  document.getElementById('dot').className='';
  document.getElementById('savetext').textContent='unsaved edits…';
  clearTimeout(window._t); window._t=setTimeout(save,1200);
});
window.addEventListener('load',()=>{
  fetch('irr_responses.json').then(r=>r.ok?r.json():{}).then(db=>{
    Object.entries((db&&db.r3)||{}).forEach(([k,v])=>{
      const el=document.querySelector(`[data-key="${k}"]`); if(el&&!el.innerHTML) el.innerHTML=v;});
  }).catch(()=>{});
});
"""


def esc(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) == "nan":
        return ""
    return html.escape(str(v))


def chip(code) -> str:
    c = CODE_COLORS.get(str(code).lower(), "#8a8a84")
    return f'<span class="codechip" style="background:{c}">{esc(str(code).lower())}</span>'


def build(corpus: str) -> None:
    # The blind-reconciled consensus workbook is the reference standard;
    # consensus codes are never edited after reconciliation.
    cons = pd.read_excel(
        DATA / f"CODED {corpus.capitalize()} IRR v8 24cases STRATIFIED N150.xlsx",
        sheet_name="Consensus")
    textcol = "text" if "text" in cons.columns else "para_text"
    old = pd.read_excel(OUT / f"irr24_{corpus}_scored.xlsx", sheet_name="scored")
    v8 = old[["unit_id", "deeper_meaning"]].rename(columns={"deeper_meaning": "v8"})
    oldnotes = old.set_index("row")["notes_on_disagreement"] if "notes_on_disagreement" in old.columns else pd.Series(dtype=object)
    v9 = pd.read_excel(CODING / f"{corpus}_paragraphs_24_llm_v9p2.xlsx")
    v9 = v9[["unit_id", "deeper_meaning", "reasoning"]].rename(
        columns={"deeper_meaning": "v9", "reasoning": "v9_reasoning"})

    m = cons.merge(v8, on="unit_id", validate="one_to_one").merge(
        v9, on="unit_id", validate="one_to_one")
    assert len(m) == 150, len(m)
    for c in ["final_code", "v8", "v9"]:
        m[c] = m[c].astype(str).str.strip().str.lower()

    k = cohen_kappa_score(m.final_code, m.v9, labels=CODES)
    raw = (m.final_code == m.v9).mean()
    m["status"] = "agree"
    m.loc[(m.final_code != m.v9) & (m.final_code != m.v8), "status"] = "carried"
    m.loc[(m.final_code != m.v9) & (m.final_code == m.v8), "status"] = "new"
    resolved = sorted(m[(m.final_code == m.v9) & (m.final_code != m.v8)].row.tolist())

    with pd.ExcelWriter(OUT / f"irr24_{corpus}_scored_v9.xlsx") as xw:
        m.to_excel(xw, sheet_name="scored", index=False)
        m[m.status != "agree"].to_excel(xw, sheet_name="disagreements_v9", index=False)

    rows_html = []
    d = m[m.status != "agree"].sort_values(["status", "row"])
    for _, r in d.iterrows():
        rw = int(r["row"])
        comment = NEW_COMMENTS.get((corpus, rw)) or (CLAUDE.get((corpus, rw), ("", "", ""))[2])
        note = esc(oldnotes.get(rw)) if rw in oldnotes.index else ""
        txt = esc(r[textcol])
        body = f"<details><summary>{txt[:200]}…</summary>{txt}</details>" if len(txt) > 450 else txt
        head = f'<div class="hl">{esc(r["headline"])}</div>' if "headline" in d.columns and esc(r.get("headline")) else ""
        rows_html.append(f"""
<tr data-st="{r.status}">
<td class="c-code"><span class="st {r.status}">{r.status.upper()}</span>
  <div>Final {chip(r.final_code)}</div><div>v8 {chip(r.v8)}</div><div>v9 {chip(r.v9)}</div></td>
<td class="c-para">{head}{body}<div class="meta">{esc(r.unit_id)} · sheet row {rw}</div></td>
<td class="c-rater">{chip(r.code_rater1)}<div class="just">{esc(r.justification_rater1) or '<span class="empty">—</span>'}</div></td>
<td class="c-rater">{chip(r.code_rater2)}<div class="just">{esc(r.justification_rater2) or '<span class="empty">—</span>'}</div></td>
<td class="c-llm">{chip(r.v9)}<div class="just">{esc(r.v9_reasoning)}</div></td>
<td class="c-claude">{esc(comment) or '<span class="empty">—</span>'}{f'<div class="meta"><b>your note last round:</b> {note}</div>' if note else ''}</td>
<td class="c-resp" contenteditable="true" data-key="{corpus}v9:{rw}" spellcheck="true"></td>
</tr>""")

    n_new = int((m.status == "new").sum()); n_car = int((m.status == "carried").sum())
    title = f"{corpus.capitalize()} IRR vs v9 instructions — {n_new + n_car} disagreements (kappa {k:.3f}, raw {raw:.0%})"
    sub = (f"Scored against the re-coded corpus (new instructions, pass 2 of 2, within-run agreement was high). "
           f"{n_new} NEW rows broke because of the instruction changes; {n_car} carried over from last round. "
           f"Resolved since last round: rows {', '.join(map(str, resolved))}. "
           f"Blue column: write flip / keep / your reasoning — autosaves via save_server.py."
           + (" Licensed article text — do not share outside the team." if corpus == "media" else ""))
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{CSS}</style></head><body>
<header><h1>{title}</h1><p class="sub">{sub}</p></header>
<div class="toolbar">
<button class="on" data-f="all" onclick="filt('all')">All {n_new + n_car}</button>
<button data-f="new" onclick="filt('new')">New ({n_new})</button>
<button data-f="carried" onclick="filt('carried')">Carried ({n_car})</button>
<span style="flex:1"></span><span id="savenote"><span id="dot"></span><span id="savetext">no edits yet</span></span></div>
<div class="wrap"><table>
<thead><tr><th>Status / codes</th><th>Paragraph</th><th>Rater 1</th><th>Rater 2</th><th>LLM v9</th><th>Claude</th><th>Your call</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table></div>
<script>{JS}</script></body></html>"""
    out = OUT / f"{corpus}_disagreements_v9.html"
    out.write_text(page)
    print(f"{corpus}: kappa={k:.3f} raw={raw:.1%} new={n_new} carried={n_car} resolved={len(resolved)} -> {out.name}")


if __name__ == "__main__":
    for corpus in (sys.argv[1:] or ["legal"]):
        build(corpus)
