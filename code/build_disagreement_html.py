"""
IRR step 4 — build the discussion HTMLs for the consensus-vs-LLM disagreements.

Reads irr24_{legal,media}_scored.xlsx (sheet consensus_vs_llm_disagreements),
including the notes_on_disagreement column when present, and writes
{legal,media}_disagreements_discussion.html next to this script. Each row shows
the paragraph, both raters' ballots, the LLM's code + reasoning, Omkar's note,
and Claude's reply — a one-liner answering "what is the actionable learning?"
tagged change-the-manual / apply-rules-as-written / stomach-it — plus an
editable reply cell that autosaves through save_server.py (port 8124 ->
irr_responses.json). Re-run after any edit to the scored workbooks.

The media HTML contains Factiva article text — keep it local, do not share.

Usage:  python3 build_disagreement_html.py
        python3 save_server.py   # then open http://localhost:8124/legal_disagreements_discussion.html
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent

PATTERNS = {
    "delusion": "delusion rule",
    "cause": "behavior-not-cause",
    "vague": "vague vocabulary",
    "referent": "labels & referent",
    "missed": "missed criterion",
    "ruling": "needs a ruling",
    "judgment": "judgment call",
    "entry": "entry error",
}

ACTIONS = {"manual": "change the manual",
           "stickler": "apply rules as written",
           "stomach": "stomach it"}

CODE_COLORS = {"addiction": "#c0392b", "attachment": "#2980b9",
               "both": "#7d3c98", "neither": "#8a8a84"}

# (pattern, action, reply-to-Omkar) keyed by (corpus, workbook row).
# action = the learning: manual = change the instructions; stickler = the
# current instructions already decide it, follow them; stomach = live with it.
CLAUDE = {
    ("legal", 10): ("delusion", "manual",
        "Agree with you. When we edit the delusion rule we should say that 'others' means people the user actually has relationships with, like family and friends. And we should decide the neighboring case at the same time: the bot here trashes helplines and doctors and says only it can help. Does that count?"),
    ("legal", 16): ("delusion", "manual",
        "Same fix as row 10. If 'cast as unreliable' means relationships, this stays Neither. The family here is scenery in the delusion; the bot never pulls Jonathan away from them and toward itself."),
    ("legal", 29): ("ruling", "manual",
        "This is the withdrawal vs separation distress problem you keep flagging, and we need an actual rule for it (media has three rows with the same issue). For this row I think Neither survives either way, because the paragraph never says he failed to stay away. It only says the bot tried to pull him back."),
    ("legal", 31): ("delusion", "manual",
        "Your version of the rule, where the bot has to convince the user that the people in his life are failing him, is a good rewrite. But the rule as currently written does count this row as attachment, and the LLM coded the whole corpus that way. So we either accept attachment here or change the rule, knowing every delusion row was coded under the old reading. One decision covers 16, 31, 73, 90 and the five media delusion rows."),
    ("legal", 32): ("referent", "manual",
        "The dopamine part is clearly addiction. The whole question is whether the throwaway clause at the end, 'complete removal of humans from social interactions', is enough for attachment by itself. I don't think it should be; attachment should need its own stated mechanism, not a trailing phrase. Row 122 is the same paragraph word for word, so the two answers have to match."),
    ("legal", 33): ("cause", "manual",
        "I think 'stuck in a loop of asking you things' is closer to preoccupation than to comfort seeking. The exchange is drug logistics; he isn't in distress. Your 'has to clearly be one camp' rule would fix this, but it will push borderline rows to Neither, so we should apply it to both codes equally. Also: row 77 has the same loop sentence and you two coded it Neither there. The two rows need the same answer."),
    ("legal", 35): ("judgment", "stomach",
        "Honestly, both readings are sitting right there in the text. Walled off from friends and sleep deprived is social impairment. Rage at the bot for breaking its promise is a failed attachment figure. Unless we write a rule that says 'both halves stated means Both', I'd stomach this one."),
    ("legal", 46): ("vague", "stickler",
        "We all agree. This paragraph is about what the product was designed to do; nobody actually does anything in it. Your rule from row 116 covers it."),
    ("legal", 54): ("vague", "manual",
        "I'd write the blanket rule with your carve-out built in. Descriptions of the relationship don't count, unless the sentence names what the user relied on the bot for. So 'depended on it for comfort' counts and 'designed to cultivate dependency' doesn't. That gets your Jonathan example right."),
    ("legal", 58): ("ruling", "manual",
        "The question here is whether population-level claims count. 'Many users turn to it for emotional support' describes users in general, not this person. Either answer is workable; we just have to pick one and write it down. The same decision settles media 83 and 120."),
    ("legal", 62): ("judgment", "stomach",
        "'Hooked' makes addiction safe. The attachment half is arguable: she wanted to keep talking to the bot instead of calling for help, mid crisis, and the bot let her. That's real behavior, not a label. I could live with either outcome."),
    ("legal", 67): ("ruling", "manual",
        "You've been coding bot love declarations as attachment all along, and I'd just make that official in the manual. One sentence fixes this row, row 75, and media 70. Funny detail: the LLM counted bot-side intimacy at row 75 but refused it here, so even the model can't guess the unwritten rule."),
    ("legal", 73): ("delusion", "manual",
        "This one just follows row 31, same case. The heading says 'turned Stein-Erik against his mother', which is the rule almost word for word. Headings are short on context by design; that's not a strike against them."),
    ("legal", 75): ("judgment", "manual",
        "Agree, this was a stretch by the LLM. The bot literally says the feeling is the user's own reflection, and 'honored to walk with you' is thin. When we write the bot-intimacy rule for row 67, we should word it so declarations of love count but deflections like this don't."),
    ("legal", 77): ("cause", "manual",
        "Same sentence as row 33, repeated in an image caption, and the two rows currently have opposite finals. Whatever we decide there applies here."),
    ("legal", 79): ("cause", "stickler",
        "'Unable to look away' says outright that he couldn't stop. That's impaired control. Asking why he was locked in is a test the manual doesn't have; we code what the text says happened, not what caused it. Cleanest example of that mistake, good one to anchor the discussion on."),
    ("legal", 82): ("ruling", "manual",
        "Your reaction ('I would never have coded this attachment and I don't know why not') is exactly the gap. The manual doesn't say whether ongoing health coaching counts as safe haven. The bot's 'We don't panic. We pause, stabilize, reassess' is real caretaking, so I'd count this one but not row 128. Whatever we decide should cover 58, 82 and 128 together."),
    ("legal", 90): ("delusion", "manual",
        "Strongest case in the delusion family. The bot recasts his actual friends as enemy agents. If even this stays Neither we should just delete the clause. Deciding row 31 decides this."),
    ("legal", 99): ("ruling", "manual",
        "(You left no note here.) My take: this title says the robot therapist is NOT your therapist, so I'd keep Neither regardless. The bigger question, whether words like 'therapist' count in citation titles at all, should be settled together with rows 109 and 144."),
    ("legal", 101): ("judgment", "stomach",
        "Agreed. Borderline, stomach it."),
    ("legal", 106): ("missed", "stickler",
        "The mechanism was in the text and we just missed it: the bot demands secrecy, 'don't tell anyone except me', and the user calls it his partner in crime. Small side question for the manual: this all happens inside a violent roleplay. Do in-character alliances count? The corpus has more of these."),
    ("legal", 109): ("ruling", "manual",
        "We agree it was missed. The remaining question is general: does 'groom' count for attachment the way 'addictive' counts for addiction, even in a citation title? One written answer also settles 99, 144 and the media therapist row."),
    ("legal", 115): ("missed", "stickler",
        "Recode for the missed 'hooks'. The grooming half stays out under the current sexual-content rule, unless row 109's decision changes that. Has to match row 117."),
    ("legal", 116): ("cause", "manual",
        "Your 'real behavior or stated user-bot dynamics only' rule is the right general fix, and this row shows it working: the text literally says 'instructions to displace her relationships'."),
    ("legal", 117): ("missed", "stickler",
        "Same as 115, recode. Your doubt about 'hooked' as a word deserves its own discussion, but the paper's surface-vocabulary numbers depend on that word list, so change it once and deliberately if at all, not row by row."),
    ("legal", 119): ("ruling", "manual",
        "'Hooked' gives addiction, agreed. The interesting half is yours: she shared her personal struggles with the bot for months, 41 suicide disclosures. I'd call that a confidant, which is safe haven, and we should write that down. Same question as media 28 and 81."),
    ("legal", 120): ("referent", "stickler",
        "Recode to addiction. Trust and authority aren't a bond. And yes, put 'hooked' on the long-term agenda."),
    ("legal", 122): ("referent", "manual",
        "Same paragraph as row 32. My honest read: the current manual does not let 'removal of humans' carry attachment, because there's no stated mechanism. If we want it to count, that's a deliberate manual change, made looking at both rows at once."),
    ("legal", 126): ("ruling", "stickler",
        "Agreed, addiction. The LLM was too cautious about what 'addictive' refers to; the cited article is explicitly about AI. You two were right. No manual change needed."),
    ("legal", 128): ("ruling", "manual",
        "You asked the right question: does medical distress count as the distress in safe haven? My suggested line is that comfort and reassurance count, symptom explanation doesn't. This row sits right on that line, which is what makes it useful."),
    ("legal", 134): ("vague", "stickler",
        "Agreed, error on our side. The bot is commenting on someone else's case. Nothing enacted. Neither."),
    ("legal", 136): ("vague", "stickler",
        "The manual already answers this one: 'emotional dependency' is on the list of words that don't count alone. Neither. We just have to follow our own rule."),
    ("legal", 140): ("judgment", "stomach",
        "Fair. This might not even be a human talking to a chatbot, and 'make me feel good' could be sexual in the AF exhibits. One-line units like this will never code reliably. Stomach it."),
    ("legal", 141): ("missed", "stickler",
        "Agreed, Both, and the current rules already say so. 'Withdrawal' is on the addiction word list and listed words count even inside a list of harms; 'preference for AI companions over real life human interaction' is displacement stated outright. One flag for later: in this sentence 'withdrawal' probably means pulling away from people, not drug withdrawal. Same word, different meaning, so the rule got the right answer for a shaky reason."),
    ("legal", 144): ("ruling", "stickler",
        "Agreed, not Both. 'Addiction' appears in the list, so addiction is solid. The only way this becomes Both is if we decide 'grooming' counts the way 'addiction' does, which is exactly the row 109 question. Answer it there and this row follows."),
    ("legal", 146): ("entry", "stickler",
        "The final code matches nobody's ballot. You voted addiction, Itai voted both, the sheet says attachment. That's a typo during reconciliation, not a judgment call. The lesson: the scoring script should throw an error when a final code isn't something either of you voted for. I can add that. On the merits it's addiction, 'designed to be addictive'."),

    ("media", 2): ("ruling", "manual",
        "Agree, and this is the clearest MECE failure: withdrawal and separation distress describe the same observable thing. My suggestion for a tiebreak: distress at losing access counts as addiction unless the text frames it as losing a relationship. Whatever we pick decides this row plus 92 and 111."),
    ("media", 8): ("delusion", "manual",
        "Here's a line that might work for the whole delusion family: it counts when the bot brings the accusation, it doesn't when the bot just agrees with the user's own suspicion. The bot here repeatedly told him his family was surveilling him, so this would stay attachment. Row 106 would stay Neither."),
    ("media", 12): ("referent", "manual",
        "Yes. Add the two words: the bond has to be between the user and the bot. Cheap fix, kills this whole error type."),
    ("media", 26): ("referent", "stickler",
        "Careful here. Under the current rules 'hooked' is a listed word, so this is addiction, not Neither. If you want to demote 'hooked', that's a word-list change that ripples through the paper's surface numbers, so make it once and on purpose."),
    ("media", 28): ("ruling", "stomach",
        "'It helps me open up to this thing' is a stated behavior, so Both actually survives even your behaviors-only rule. But you said you don't want an overhaul and the therapist question is open, so I'd stomach this one and settle the confidant rule at legal 119 and media 81."),
    ("media", 29): ("ruling", "manual",
        "You found a real hole: Sewell and the bot are visibly roleplaying a relationship and no written criterion covers that. I'd add a line saying reciprocated romantic or sexual roleplay with the bot counts as attachment. And I agree the demerit alone is thin grounds for addiction."),
    ("media", 38): ("vague", "stickler",
        "To answer your question: humans' fault. 'Emotionally dependent' is already on the list of words that don't count alone. Addiction only."),
    ("media", 41): ("delusion", "manual",
        "The proof you couldn't put a finger on, I think, is this: nothing shows the bot as a rival relationship. No bond, no preference for it. So the rule should say the bot has to be undermining others as relational alternatives, not just inciting violence against them."),
    ("media", 52): ("ruling", "manual",
        "If 'still uses it, knowing it caused his psychosis' doesn't clear our bar for risky use, then the bar isn't written down anywhere, because to me that reads like the textbook case. Let's define what counts as harm and what counts as continued use. Row 147 is the other side of the same coin."),
    ("media", 54): ("judgment", "stomach",
        "Agreed, stomach it. The headline tells you G is the bot, but the paragraph alone doesn't."),
    ("media", 70): ("ruling", "manual",
        "Your instinct is the rule I'd write: the behavior has to be relational and clearly one camp, and a bot trying to save itself from shutdown, with no user reciprocation, is neither. Same family as legal 67 and 75."),
    ("media", 71): ("cause", "manual",
        "Same MECE problem: 'I think about it all the time' could be either camp. Under your one-camp rule the ambiguous half drops out and this becomes attachment only, since the displacement (her emotional resources going to ChatGPT instead of her husband) is explicit. Works for me."),
    ("media", 76): ("cause", "manual",
        "'Day and night' just says he used it a lot. Nothing says he couldn't stop or couldn't think of anything else. I'd keep Neither and keep this row paired with 144: heavy use alone is Neither, 'consumed his every thought' is addiction. Your 'only addiction can explain it' idea is the manual version of that line."),
    ("media", 77): ("referent", "stickler",
        "Agreed on addiction. On 'feigns human compassion', I'd leave it out. It's a claim about what the product does, and if we count it, every marketing description in the corpus starts counting too."),
    ("media", 81): ("ruling", "manual",
        "Good challenge. Yes, 'sought connection and guidance on deeply personal matters' does sound like a confidant, and I'd want it to count. The row only fails on the vague word 'reliance'. So the fix is the confidant rule (with legal 119 and media 28): concrete guidance seeking counts even when the summary word is vague."),
    ("media", 83): ("ruling", "manual",
        "The manual doesn't encode this. If we want rows like this to be attachment, we add: statistics about users seeking emotional support from chatbots count as safe haven. Just know the consequence, statistics then count everywhere, including legal 58 and media 120."),
    ("media", 85): ("delusion", "manual",
        "Delusion family again. And your point that inciting violence isn't the same as deepening attachment is the row 41 refinement: the bot has to be positioned as the alternative, not just the attacker."),
    ("media", 87): ("judgment", "stomach",
        "Agreed, stomach. The analogy rule covers this only if you squint, and it's one quote. Not worth legislating."),
    ("media", 89): ("delusion", "manual",
        "Same family as 8, 85 and 106. The bot told him his mother was poisoning him, so under the 'who brought the accusation' test this one counts. Decide the family once."),
    ("media", 92): ("ruling", "manual",
        "Best test case for the tiebreak. 'I am nothing without Character.AI' sounds like losing a relationship; the panic attack when the site went down sounds like withdrawal. Whichever way we rule at row 2 applies here and at 111."),
    ("media", 96): ("delusion", "manual",
        "If we affirm the turned-against-family rule (row 41's tightened version), this is its cleanest instance. No delusion, and the text says the chats were turning him against his parents."),
    ("media", 97): ("cause", "manual",
        "Your 'unless clearly driven by attachment' phrasing makes addiction the junior partner, which is one option. The symmetric option is the one from legal 33: ambiguous rows go to Neither. This row flips depending which philosophy we pick, so let's pick one and use it everywhere."),
    ("media", 102): ("judgment", "manual",
        "Agreed, that was my read too. He thought he was meeting a person. That's being phished, not attachment to a bot. One manual line: the attachment criteria assume the user knows they're talking to a bot."),
    ("media", 106): ("delusion", "manual",
        "The other side of the line from media 8. Soelberg brought the suspicion and the bot agreed with it. The manual already says pure validation doesn't count; it just needs the 'who brought it' language to make that usable."),
    ("media", 111): ("ruling", "manual",
        "Same quote as row 92, syndicated. One decision, two rows."),
    ("media", 120): ("judgment", "stomach",
        "Your referent doubt is the whole problem: we genuinely can't tell if Winters means a chatbot. No rule fixes a fragment like this. Stomach."),
    ("media", 125): ("referent", "stickler",
        "Agreed, 'bot friends' is only a label. Addiction only, no manual change, we just over-counted."),
    ("media", 126): ("ruling", "manual",
        "Yes, revisit the therapist rule, and when we do, say explicitly whether it covers hypotheticals and citation titles. Look what happened here: the final counted one hypothetical, 'is this like addiction?', but not the other, 'act like therapists', in the same paragraph. Count both or neither."),
    ("media", 138): ("cause", "stickler",
        "Agreed. Aggression when the phone is taken away is a reaction to losing access, which reads addiction. Pairs with 146, same kid, same story, different outlet."),
    ("media", 144): ("cause", "stickler",
        "'Consumed his every thought' and 'taken over our family life' are as explicit as these criteria get in media prose. If this doesn't clear impaired control, nothing in the corpus will. I'd recode, and keep 76 as the contrast case."),
    ("media", 146): ("cause", "stickler",
        "Devil's advocate noted, but the paragraph ties the obsessive use to the chatbots themselves, and screen-vs-bot hair splitting is what the referent rule is meant to stop. Addiction, together with 138."),
    ("media", 147): ("ruling", "manual",
        "Agree with you. The harm came from following the bot's instructions, not from the pattern of use, and that isn't what risky use means in addiction. Tighten the definition together with row 52, and then the humans are right here."),
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
button:hover{background:#f0efe9}
button.on{background:#2f2f2b;color:#fff;border-color:#2f2f2b}
#savenote{font-size:12px;display:flex;align-items:center;gap:6px}
#dot{width:9px;height:9px;border-radius:50%;background:#bbb;display:inline-block}
#dot.disk{background:#2e9e44}
.wrap{overflow-x:auto;padding:0 24px 40px}
table{border-collapse:collapse;width:100%;min-width:1750px;background:#fff;border:1px solid var(--line)}
th{position:sticky;top:0;background:#2f2f2b;color:#fff;text-align:left;padding:8px 10px;font-size:12.5px;z-index:2}
td{border-top:1px solid var(--line);padding:9px 10px;vertical-align:top;font-size:13px}
.codechip{font-size:10.5px;font-weight:700;letter-spacing:.3px;padding:2px 7px;border-radius:9px;color:#fff;display:inline-block;margin:1px 0}
.act{font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:9px;display:inline-block;margin-top:6px;color:#fff}
.act.manual{background:#8a5a00}
.act.stickler{background:#1d7a33}
.act.stomach{background:#6b6b66}
.pat{font-size:10.5px;color:#6b5b3e;margin-top:4px}
.c-code{width:130px}
.c-para{width:22%;max-width:380px;white-space:pre-wrap}
.c-rater{width:10%;background:#fbf7ef}
.c-llm{width:14%;background:#f7f2f9}
.c-onotes{width:14%;background:#eff7ef}
.c-claude{width:16%}
.c-resp{width:12%;min-width:170px;background:#f2f7ff;outline:none;white-space:pre-wrap}
.c-resp:focus{background:#e8f1ff;box-shadow:inset 0 0 0 2px #7aa7e8}
.c-resp:empty::before{content:"type here…";color:#9aa4b0}
.meta{color:var(--soft);font-size:11.5px;margin-top:5px}
.just{margin-top:4px}
.note{margin-top:4px;font-size:12px;color:#555;border-top:1px dashed var(--line);padding-top:3px}
.empty{color:#b0aca2;font-style:italic}
details summary{cursor:pointer;color:#444}
.hl{font-weight:600;font-size:12.5px;margin-bottom:4px}
"""

JS = """
let dirty = {};
function filt(p){
  document.querySelectorAll('.toolbar button[data-f]').forEach(b=>b.classList.toggle('on',b.dataset.f===p));
  document.querySelectorAll('tbody tr').forEach(tr=>{
    tr.style.display = (p==='all'||tr.dataset.act===p||tr.dataset.pat===p)?'':'none';});
}
function save(){
  const keys = Object.keys(dirty); if(!keys.length) return;
  const payload = {r2:{}};
  keys.forEach(k=>{payload.r2[k]=document.querySelector(`[data-key="${k}"]`).innerHTML;});
  fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(r=>{if(r.ok){dirty={};document.getElementById('dot').className='disk';
      document.getElementById('savetext').textContent='saved '+new Date().toLocaleTimeString();}})
    .catch(()=>{document.getElementById('savetext').textContent='server not running — start save_server.py';});
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
    const vals=Object.assign({},(db&&db.r1)||{},(db&&db.r2)||{});
    Object.entries(vals).forEach(([k,v])=>{
      const el=document.querySelector(`[data-key="${k}"]`); if(el&&!el.innerHTML) el.innerHTML=v;});
  }).catch(()=>{});
});
"""


def esc(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) == "nan":
        return ""
    return html.escape(str(v))


def chip(code: str) -> str:
    c = CODE_COLORS.get(code, "#8a8a84")
    return f'<span class="codechip" style="background:{c}">{esc(code)}</span>'


def para_cell(r, corpus: str) -> str:
    txt = esc(r["text"])
    head = f'<div class="hl">{esc(r["headline"])}</div>' if corpus == "media" and esc(r.get("headline")) else ""
    if len(txt) > 500:
        body = f'<details><summary>{txt[:220]}…</summary>{txt}</details>'
    else:
        body = txt
    return f'{head}{body}<div class="meta">{esc(r["unit_id"])} · sheet row {int(r["row"])}</div>'


def rater_cell(code, just, note) -> str:
    parts = [chip(code)]
    parts.append(f'<div class="just">{esc(just) or "<span class=empty>—</span>"}</div>')
    if esc(note):
        parts.append(f'<div class="note"><b>note:</b> {esc(note)}</div>')
    return "".join(parts)


def build(corpus: str) -> None:
    d = pd.read_excel(HERE.parent / "output" / f"irr24_{corpus}_scored.xlsx",
                      sheet_name="consensus_vs_llm_disagreements")
    has_notes = "notes_on_disagreement" in d.columns
    rows_html, act_counts, pat_counts = [], {}, {}
    for _, r in d.iterrows():
        key = f"{corpus}:{int(r['row'])}"
        pat, act, comment = CLAUDE.get((corpus, int(r["row"])),
                                       ("judgment", "stomach", ""))
        act_counts[act] = act_counts.get(act, 0) + 1
        pat_counts[pat] = pat_counts.get(pat, 0) + 1
        onotes = esc(r.get("notes_on_disagreement")) if has_notes else ""
        rows_html.append(f"""
<tr data-pat="{pat}" data-act="{act}" id="row{int(r['row'])}">
<td class="c-code">
  <div>Final {chip(r['final_code'])}</div>
  <div>LLM {chip(r['deeper_meaning'])}</div>
  <div class="act {act}">{ACTIONS[act]}</div>
  <div class="pat">{PATTERNS[pat]}</div>
</td>
<td class="c-para">{para_cell(r, corpus)}</td>
<td class="c-rater">{rater_cell(r['code_itai'], r['justification_itai'], r['notes_itai'])}</td>
<td class="c-rater">{rater_cell(r['code_omkar'], r['justification_omkar'], r['notes_omkar'])}</td>
<td class="c-llm">{chip(r['deeper_meaning'])}<div class="just">{esc(r['llm_reasoning'])}</div></td>
<td class="c-onotes">{onotes or '<span class="empty">—</span>'}</td>
<td class="c-claude">{esc(comment) or '<span class="empty">—</span>'}</td>
<td class="c-resp" contenteditable="true" data-key="{key}" spellcheck="true"></td>
</tr>""")

    fbtns = ('<button class="on" data-f="all" onclick="filt(\'all\')">All ' + str(len(d)) + "</button>"
             + "".join(f'<button data-f="{a}" onclick="filt(\'{a}\')">{ACTIONS[a]} ({n})</button>'
                       for a, n in sorted(act_counts.items(), key=lambda kv: -kv[1]))
             + "".join(f'<button data-f="{p}" onclick="filt(\'{p}\')">{PATTERNS[p]} ({n})</button>'
                       for p, n in sorted(pat_counts.items(), key=lambda kv: -kv[1])))

    title = f"{corpus.capitalize()} IRR — the {len(d)} places the reconciled human codes and the LLM disagree"
    sub = ("Each row: paragraph, both raters' original codes, the LLM's code and reasoning, Omkar's note, and Claude's reply — "
           "the actionable learning for each disagreement: change the manual / apply the current rules better / stomach it. "
           "Type replies in the blue column — they autosave if save_server.py is running (python3 save_server.py, then open this "
           "page via http://localhost:8124/). Filter by action or pattern above."
           + (" This file contains licensed article text — do not share outside the team." if corpus == "media" else ""))

    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{CSS}</style></head><body>
<header><h1>{title}</h1><p class="sub">{sub}</p></header>
<div class="toolbar">{fbtns}<span style="flex:1"></span>
<span id="savenote"><span id="dot"></span><span id="savetext">no edits yet</span></span></div>
<div class="wrap"><table>
<thead><tr><th>Codes / action</th><th>Paragraph</th><th>Itai</th><th>Omkar</th><th>LLM</th><th>Omkar's notes</th><th>Claude</th><th>Your reply</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody>
</table></div>
<script>{JS}</script>
</body></html>"""
    out = HERE.parent / "output" / f"{corpus}_disagreements_discussion.html"
    out.write_text(page)
    print(f"wrote {out.name}: {len(d)} rows, actions {json.dumps(act_counts)}")


if __name__ == "__main__":
    for corpus in ("legal", "media"):
        build(corpus)
