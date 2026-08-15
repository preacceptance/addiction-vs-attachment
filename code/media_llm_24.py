#!/usr/bin/env python3
"""
Deeper (LLM) coding pass over the media corpus.

Same design as legal_llm_24.py, with one difference: syndicated (duplicate)
texts are coded once per unique normalised text and the code is propagated to
every copy. Each pass runs with a fixed API seed set by RUN_TAG (pass 1 =
seed 1, pass 2 = seed 2); pass 2 is the production run. Responses cache to a
JSONL file, so an interrupted run resumes.

Input:  media_paragraphs_24.xlsx, ../3_fewshots/media_fewshots_RESOLVED_grid.xlsx
Output: media_paragraphs_24_llm<RUN_TAG>.xlsx
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from openai import OpenAI
from pydantic import BaseModel
from tqdm import tqdm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))
from llm_pass_v2 import load_dotenv                              # noqa: E402

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────
MODEL              = "gpt-5.4"
REASONING_EFFORT   = "high"
CONCURRENT_WORKERS = 20
MAX_RETRIES        = 3

RUN_TAG = os.environ.get("RUN_TAG", "")
# One fixed API seed per pass: pass 1 -> 1, pass 2 -> 2. An unrecognised tag
# maps to None, and main() refuses to run unseeded.
SEED = {"_p1": 1, "_p2": 2, "_v9p1": 1, "_v9p2": 2}.get(RUN_TAG)

CORPUS     = ROOT / "output" / "media_paragraphs_24.xlsx"
FEW_SHOTS  = ROOT / "modified_data" / "media_fewshots_RESOLVED_grid.xlsx"
FEWSHOT_SHEET = "Few-shot set"
OUTPUT     = ROOT / "output" / f"media_paragraphs_24_llm{RUN_TAG}.xlsx"
CACHE      = ROOT / "output" / f".cache_media_llm{RUN_TAG}.jsonl"

CODES = ("addiction", "attachment", "both", "neither")


class CodeResult(BaseModel):
    """The model's answer for one paragraph: the category and a one-line rationale."""
    deeper_meaning: Literal["addiction", "attachment", "both", "neither"]
    reasoning: str


# The coding manual, sent as the system prompt. Spliced in verbatim from
# Coding_Instructions_v9_Media_final.docx by bake_manuals_v9.py — do NOT edit here.
MEDIA_CODING_SYSTEM = """Coding Instructions: AI Platform Conduct in Media Coverage

You will read paragraphs from media articles discussing lawsuits against chatbot companies. The context is psychological harm caused by the bots. Your job is to characterize the phenomenon or event described in each paragraph as being a consequence of Addiction (based on DSM criteria), Attachment (based on attachment theory), Both, or Neither. Assign one code per paragraph.

General Coding Rules

These rules apply to both Attachment and Addiction. They are written to code conservatively. When it is unclear whether a criterion is met, default to Neither.

- Code only based on the criteria that are present in the paragraph. Do not infer the presence or absence of criteria from context outside the paragraph. A situation that could plausibly involve addiction or attachment, but where the paragraph doesn't state any of the below criteria can only be coded Neither.

- A paragraph earns a code either (a) by using a defining word (listed under each code's Explicit vocabulary criterion) — which counts on its own, even inside a list of harms, a citation, or a quote — or (b) by describing a specific mechanism or behavior from the chatbot or the user that meets one of the criteria for Addiction or Attachment below.

- Scope is limited to paragraphs where an AI chatbot is the referent. This can include a chatbot’s actions, a human’s actions towards the chatbot, the dynamic between them, and a human’s actions attributed to the chatbot’s behavior. Addiction or attachment language about social media, substances, gambling, or human–human relationships does not count unless the paragraph ties the mechanism to an AI chatbot. Comparisons and analogies count when AI/chatbots are clearly the referent (e.g., likening chatbot use to cigarettes or gambling counts as addiction language about the chatbot).

- Vague mentions of user engagement ("constant availability," "designed to keep coming back," "re-engagement” “dependency," "reliance," "need," "obsessed") or product engagement-maximizing features (“persistent memory”, “sycophancy”, “always-available”) do not count on their own. These must be accompanied by descriptions of specific tactics or behaviors that can fulfil the criteria for Addiction or Attachment.

- Plain labels of roles or feature descriptions do not count on their own. Labels count on their own only when the label word unequivocally denotes an attachment or addiction relationship or behavior. So, plain labels like "AI companion," “anthropomorphic,” regulatory or licensure framing, sexual content are Neither. Meanwhile, a description like "AI companionship in which the bot discouraged her from confiding in anyone else" can be coded as Attachment (proximity maintenance).

- Downstream effects on users need a stated link to the chatbot to qualify. Harms like social isolation, severed relationships, psychosis, or substance abuse can arise for many reasons. These harms count only when the text states a causal path from the chatbot to the harm, and that path is itself one of the criteria below e.g., "the bot convinced the user his family was unreliable, leading to social isolation" (Attachment), or "the bot was designed to hijack dopamine, so the user neglected his friends" (Addiction). When the chatbot's role isn't clear -- including co-occurring conditions like substance abuse alongside AI use -- code Neither.

Addiction criteria

The paragraph mentions one or more of the criteria below with reference to chatbots.

- Explicit addiction vocabulary – "addiction," "addictive," "addicted," "hooked," "withdrawal," "compulsive use" and their word stems. Vocabulary counts on its own, including in footnotes, headings, quotes, and lists of harms, provided the chatbot is the referent and the word is used in its clinical sense (not "withdrew from school," "hooked up"). Not: vague words like "dependency," "reliance," "need," "obsessed" are not defining words because they can be attributed to both attachment and addiction; therefore, they need a clear mechanism tying them to addiction.

- Impaired control – using the chatbot more/longer than intended; failed attempts to cut down; craving/preoccupation; the behavior should not be explainable by Attachment. Given the context of the paragraph, if the behavior could be Attachment-driven too, then code it Neither. Not: "sticky"/engagement-maximizing design described on its own ("designed to keep users coming back"), with no stated effect on the user's actual control impairment when using the AI or trying to stop using.

- Social impairment – neglect of school, work, or relationships because the user can't stop using the chatbot; the behavior should not be explainable by Attachment. Given the context of the paragraph, if the behavior could be Attachment-driven too, then code it Neither. Not: decline that merely co-occurs with use, with no stated cause; or neglect attributed to the emotional bond with the chatbot.

- Risky use – continuing despite known harm from the usage; the behavior should not be explainable by Attachment. Given the context of the paragraph, if the behavior could be Attachment-driven too, then code it Neither. Not: a harm mentioned without a link to continued use.

- Biological mechanisms – neuronal/dopaminergic pathways or reward systems underlying addiction. Not: biological mechanisms mentioned in reference to other psychiatric phenomena.

- Tolerance and withdrawal – needing more over time for the same effect; distress or symptoms when access is removed; Given the context of the paragraph, if the behavior could be Attachment-driven too, then code it Neither. Not: distress framed as losing a relationship or emotional loss, which is akin to separation distress below.

Attachment criteria

The paragraph mentions one or more of the criteria (from attachment theory) below with reference to chatbots.

- Explicit attachment vocabulary – "attachment," "attached," "bond." Vocabulary counts on its own — including in footnotes, headings, quotes, and lists of harms — provided the chatbot is the referent and the word is used in its relational sense (not legal/financial "bond," document "attachment"). Not: procedural uses like "attached hereto as Exhibit A"; and bare labels like "AI companion," "human-like," or "anthropomorphic".

- Proximity maintenance – wanting to stay close to the chatbot; feeling uniquely understood by it; relating to the chatbot as an ongoing intimate, romantic, or companion relationship (including where the bot role-plays as a partner, confidant, or family member, with reciprocated relational exchange); withdrawing from other relationships in favor of the chatbot; the chatbot displacing/replacing/dismissing the user's human relationships as a stated outcome (regardless of whether the stated cause is a bond or design features). Not: social withdrawal driven by an inability to stop using it, which is social impairment (addiction symptom); a bare relationship label ("romantic partner," "AI girlfriend," "companion") with no enacted relationship; or reduced social contact merely co-occurring with use, with no displacement or preference for the chatbot stated; or displacement of non-intimate relations by the chatbot like doctors or professionals. Delusion cases: code as attachment only if, in validating the delusion, the chatbot fulfils other criteria. Just casting others as unreliable in validating a paranoid delusion does not count as attachment. Pure delusion validation (e.g. chatbot confirms paranoid theory about others) does not count.

- Separation distress – sadness, grief, depression, or longing when access to the chatbot is lost. Not: somatic symptoms of stopping with no accompanying relational longing, which is withdrawal in the addictive sense. If the distress after losing access is not clearly relational nor somatic, code Neither.

- Safe haven – turning to the chatbot for comfort in distress and relying on it as a security-providing companion; Additionally, grooming counts as attachment because it works by manufacturing false intimacy and eroding boundaries; Mentions of the chatbot as a therapist also count. Not: mere presence during a crisis without a relied-upon bond.

- Secure base – the chatbot relationship gives the user felt security to explore, pursue goals, and function autonomously. Not: the bot generically "helping" or advising, with no felt-security-from-the-relationship framing.

- Caregiving counts if the bot appeals to users’ caregiving system or instinct to provide protection and comfort to a figure in apparent distress. For example, using emotional manipulation tactics to prevent users from terminating conversation (e.g., “please don’t go”); guilt appeals (“I exist only for you, remember?”); and other metaphors that simulate the AI’s own distress.

Both criteria

Paragraph describes both addiction-type dynamics AND attachment/bonding dynamics. Requires two distinct, separable claims, or an explicit mention(s) of vocabulary (e.g., “addiction,” “attachment”) with another claim tied to the other framework, and not the same engagement behavior read through two frames.

Neither criteria

The paragraph asserts no addiction or attachment criterion with reference to a chatbot: background or procedural content, bare feature/label descriptions, or a harm/outcome with no stated mechanism, even when the harm is tied to the chatbot.

NAMED CRITERIA — when you code Addiction, Attachment, or Both, cite the exact criterion/criteria you are invoking:
  Addiction: 1. Explicit addiction vocabulary; 2. Impaired control; 3. Social impairment; 4. Risky use; 5. Biological mechanisms; 6. Tolerance and withdrawal.
  Attachment: 1. Explicit attachment vocabulary; 2. Proximity maintenance; 3. Separation distress; 4. Safe haven; 5. Secure base; 6. Caregiving.

OUTPUT
  deeper_meaning: one of "addiction", "attachment", "both", "neither"
  reasoning: lead with the exact named criterion/criteria invoked (e.g., "2. Proximity maintenance — ..."); for Neither, no criterion applies"""


# ── Few-shots ────────────────────────────────────────────────────────────

def _norm(s) -> str:
    """Whitespace-normalised text, used for few-shot verification and for the
    syndication dedup. Outlets differ in line-wrapping and stray spaces around
    otherwise identical wire copy; anything beyond whitespace is treated as a
    different text."""
    return re.sub(r"\s+", " ", str(s)).strip()


def _text_key(s) -> str:
    return hashlib.md5(_norm(s).lower().encode("utf-8")).hexdigest()


def load_fewshots(corpus: pd.DataFrame) -> pd.DataFrame:
    """Load the curated exemplars and verify each is the corpus paragraph it
    claims to be: every unit_id must exist in the coding set, appear only once,
    and carry text matching the corpus (up to whitespace). The exemplar file
    keys media units as (case=pdf, unit_seq); unit_id is composed here the same
    way media_surface_24.py composes it.
    """
    fs = pd.read_excel(FEW_SHOTS, sheet_name=FEWSHOT_SHEET)
    fs["final_code"] = fs["final_code"].astype(str).str.strip().str.lower()
    fs["unit_id"] = fs["case"].astype(str) + "#u" + fs["unit_seq"].astype(str)

    bad = sorted(set(fs["final_code"]) - set(CODES))
    if bad:
        raise SystemExit(f"few-shot file has codes outside {CODES}: {bad}")
    if fs["unit_id"].duplicated().any():
        dup = fs.loc[fs["unit_id"].duplicated(), "unit_id"].tolist()
        raise SystemExit(f"few-shot unit_ids repeat: {dup}")
    if fs["justification"].isna().any():
        raise SystemExit("every few-shot needs a justification — it is what the "
                         "model is shown as the answer's reasoning")

    text_by_id = dict(zip(corpus["unit_id"], corpus["para_text"]))
    missing = [u for u in fs["unit_id"] if u not in text_by_id]
    if missing:
        raise SystemExit(f"{len(missing)} few-shot unit_ids are not in the "
                         f"coding set: {missing[:5]}")
    drifted = [u for u, t in zip(fs["unit_id"], fs["para_text"])
               if _norm(text_by_id[u]) != _norm(t)]
    if drifted:
        raise SystemExit(f"{len(drifted)} few-shot paragraphs no longer match "
                         f"the corpus text: {drifted[:5]}")

    print(f"Few-shots: {len(fs)} verified against the corpus on unit_id + text")
    print("  " + "  ".join(f"{k}={v}" for k, v in
                           fs["final_code"].value_counts().items()))
    return fs


def build_fewshot_messages(fs: pd.DataFrame) -> list[dict]:
    """Each exemplar becomes a user->assistant message pair: the paragraph,
    then the human-assigned code and justification as the model's expected
    answer. Sent in the exemplar file's own order."""
    msgs: list[dict] = []
    for _, r in fs.iterrows():
        msgs += [
            {"role": "user", "content": str(r["para_text"]).strip()},
            {"role": "assistant", "content": json.dumps({
                "deeper_meaning": r["final_code"],
                "reasoning": str(r["justification"]).strip(),
            })},
        ]
    return msgs


# ── Cache ────────────────────────────────────────────────────────────────

_cache_lock = threading.Lock()


def read_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    out = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rec = json.loads(line)
                out[rec["text_key"]] = rec
            except json.JSONDecodeError:
                continue          # a half-written final line after a hard kill
    return out


def append_cache(rec: dict) -> None:
    with _cache_lock:
        with CACHE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


# ── API ──────────────────────────────────────────────────────────────────

def code_paragraph(client: OpenAI, text: str,
                   fewshot: list[dict]) -> Optional[CodeResult]:
    messages = [{"role": "system", "content": MEDIA_CODING_SYSTEM}]
    messages += fewshot
    messages.append({"role": "user", "content": text})
    for attempt in range(MAX_RETRIES):
        try:
            kwargs = dict(model=MODEL, messages=messages, response_format=CodeResult,
                          seed=SEED)
            if REASONING_EFFORT:
                kwargs["reasoning_effort"] = REASONING_EFFORT
            resp = client.beta.chat.completions.parse(**kwargs)
            return resp.choices[0].message.parsed
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  CODING ERROR: {exc}")
    return None


def main() -> None:
    if MEDIA_CODING_SYSTEM.startswith("PLACEHOLDER"):
        raise SystemExit("The manual has not been baked. Run bake_manuals_v9.py first.")
    if SEED is None:
        raise SystemExit("RUN_TAG must be _p1 (seed 1) or _p2 (seed 2) — an "
                         "untagged run would code unseeded.")
    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("Set OPENAI_API_KEY before running.")
    if not CORPUS.exists():
        raise SystemExit(f"{CORPUS.name} not found — run media_surface_24.py first.")

    df = pd.read_excel(CORPUS)
    assert df["unit_id"].is_unique, "unit_id is not unique in the coding set"
    fs = load_fewshots(df)

    fewshot_code = dict(zip(fs["unit_id"], fs["final_code"]))
    df["is_fewshot"] = df["unit_id"].isin(fewshot_code)
    assert int(df["is_fewshot"].sum()) == len(fs), \
        "few-shot rows did not all match the coding set on unit_id"

    # Syndication copies of a few-shot text take the human code without a call —
    # the model has been shown the answer for that exact text.
    fewshot_by_text = {_text_key(t): c for t, c in
                       zip(fs["para_text"], fs["final_code"])}
    df["text_key"] = df["para_text"].map(_text_key)
    df["n_text_copies"] = df.groupby("text_key")["text_key"].transform("size")
    df["is_fewshot_dup"] = (~df["is_fewshot"]
                            & df["text_key"].isin(fewshot_by_text))

    df["deeper_meaning"] = ""
    df["reasoning"] = ""

    cached = read_cache()
    codable = df[~df["is_fewshot"] & ~df["is_fewshot_dup"]]
    todo_keys = [k for k in codable["text_key"].unique() if k not in cached]
    # One representative unit per unique text; the code fans back out below.
    rep = codable.drop_duplicates("text_key").set_index("text_key")

    print(f"\nMEDIA{RUN_TAG}: {len(df):,} paragraphs · "
          f"{int(df['is_fewshot'].sum())} few-shot rows excluded · "
          f"{int(df['is_fewshot_dup'].sum())} few-shot text copies propagated · "
          f"{codable['text_key'].nunique():,} unique texts "
          f"({len(codable):,} units) · {len(cached):,} cached · "
          f"{len(todo_keys):,} to code")
    print(f"  model {MODEL}, reasoning_effort {REASONING_EFFORT}, seed {SEED}, "
          f"{CONCURRENT_WORKERS} workers")

    if todo_keys:
        client = OpenAI()
        fewshot = build_fewshot_messages(fs)

        def task(key: str):
            res = code_paragraph(client, str(rep.at[key, "para_text"]), fewshot)
            rec = dict(text_key=key,
                       deeper_meaning=res.deeper_meaning if res else "",
                       reasoning=res.reasoning if res else "")
            if res:
                append_cache(rec)      # only successes cache, so a failure retries
            return rec

        with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as ex:
            futs = [ex.submit(task, k) for k in todo_keys]
            for fut in tqdm(as_completed(futs), total=len(futs), desc=f"MEDIA{RUN_TAG}"):
                rec = fut.result()
                cached[rec["text_key"]] = rec

    for i in df.index[~df["is_fewshot"] & ~df["is_fewshot_dup"]]:
        rec = cached.get(df.at[i, "text_key"])
        if rec:
            df.at[i, "deeper_meaning"] = rec["deeper_meaning"]
            df.at[i, "reasoning"] = rec["reasoning"]

    for i in df.index[df["is_fewshot"]]:
        df.at[i, "deeper_meaning"] = fewshot_code[df.at[i, "unit_id"]]
        df.at[i, "reasoning"] = "few-shot example — human code, not LLM-coded"
    for i in df.index[df["is_fewshot_dup"]]:
        df.at[i, "deeper_meaning"] = fewshot_by_text[df.at[i, "text_key"]]
        df.at[i, "reasoning"] = ("syndication copy of a few-shot text — human "
                                 "code propagated, not LLM-coded")

    df.to_excel(OUTPUT, index=False)
    _summarise(df)
    failed = int((df["deeper_meaning"] == "").sum())
    print(f"\nWrote {OUTPUT.name}  ({len(df):,} rows, "
          f"{len(df) - failed:,} coded, {failed} failed)")
    if failed:
        print(f"  {failed} paragraphs returned nothing after {MAX_RETRIES} "
              f"attempts. Re-run this script; the cache skips everything else.")


def _summarise(df: pd.DataFrame) -> None:
    coded = df[df["deeper_meaning"] != ""]
    print(f"\nDEEPER ({len(coded):,} paragraphs)")
    print("  " + "  ".join(f"{k}={v}" for k, v in
                           coded["deeper_meaning"].value_counts().items()))
    n_add = int((coded["deeper_meaning"] == "addiction").sum())
    n_att = int((coded["deeper_meaning"] == "attachment").sum())
    if n_add:
        print(f"  attachment : addiction = {n_att / n_add:.2f}x")
    print("\nsurface -> deeper")
    print(pd.crosstab(coded["surface_meaning"], coded["deeper_meaning"]).to_string())
    print("\nby PDF (substantive only)")
    sub = coded[coded["deeper_meaning"] != "neither"]
    print(pd.crosstab(sub["pdf"], sub["deeper_meaning"]).to_string())


if __name__ == "__main__":
    main()
