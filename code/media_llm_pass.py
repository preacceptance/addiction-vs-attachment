#!/usr/bin/env python3
"""Classify each paragraph of the media-article corpus as addiction, attachment,
both, or neither. Same coding step as the legal pass — it reuses code_paragraph
from llm_pass_v2 — but on the media corpus with the media coding manual.

Input:  modified_data/media_paragraphs.xlsx  (only usable, non-duplicate rows are coded)
Output: output/media_paragraphs_llm.xlsx     (same rows + deeper_meaning, reasoning)

The request sent to the model is MEDIA_CODING_SYSTEM (generated from the manual
.docx by dev/bake_manuals.py — edit the docx, not this file) plus the few-shot
examples in MEDIA_FEWSHOT. Set RUN_TAG (e.g. "_p1") to save a run under its own
filename so two independent passes can be compared. Requires OPENAI_API_KEY.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent

# Load .env (same homebrew loader pattern as llm_pass_v2.py)
_env_file = ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from llm_pass_v2 import (
    code_paragraph,
    _safe_str,
    CONCURRENT_WORKERS,
)

# RUN_TAG suffixes the output + checkpoint filenames so the two within-LLM
# reliability passes (RUN_TAG=_p1, _p2) don't clobber each other or share a
# checkpoint. Default "" = canonical production output.
RUN_TAG = os.environ.get("RUN_TAG", "")

MEDIA_INPUT    = ROOT / "modified_data" / "media_paragraphs.xlsx"
# Hand-coded few-shot examples shown to the model. These paragraphs are excluded
# from coding and keep their human code in the output.
MEDIA_FEWSHOT  = ROOT / "modified_data" / "media_fewshot_v7.xlsx"
MEDIA_OUTPUT   = ROOT / "output" / f"media_paragraphs_llm{RUN_TAG}.xlsx"
CHECKPOINT     = ROOT / "output" / f"_media_checkpoint{RUN_TAG}.csv"
CHECKPOINT_EVERY = 500

# The coding manual, sent as the system prompt. Auto-generated from the manual
# .docx by dev/bake_manuals.py — do NOT edit the text here; edit the .docx and
# re-run the baker.
MEDIA_CODING_SYSTEM = """Coding Instructions: AI Platform Conduct in Media Coverage

You will read paragraphs from media articles discussing lawsuits against chatbot companies. Your job is to characterize the phenomenon described in each paragraph. Classify each paragraph as Addiction (based on DSM criteria), Attachment (based on attachment theory), Both, or Neither. Assign one code per paragraph.

General Coding Rules

These rules apply to both Attachment and Addiction. They are written to code conservatively. When the evidence is ambiguous, default to Neither.

- Code only based on the criteria the paragraph asserts explicitly. A situation that could plausibly involve addiction or attachment, but where the paragraph doesn't state any of the below criteria can only be coded Neither.

- A paragraph earns a code either (a) by using a defining word (listed under each code's Explicit vocabulary criterion) — which counts on its own, even inside a list of harms, a citation, or a quote — or (b) by describing a specific mechanism that meets one of the criteria below. Nothing else qualifies. Engagement words ("constant availability," "designed to keep coming back," "re-engagement") and vague words ("dependency," "reliance," "need," "obsessed") do not count on their own.

- Features and labels on their own are Neither. A design feature, product label, or surface description, not tied to a criterion, does not count — including "AI companion"/anthropomorphic/persistent-memory descriptions, a therapist label or "acts as a therapist," regulatory or licensure framing, sexual content, and sycophancy or validation.

- Scope is limited to AI chatbots only. Addiction or attachment language about social media, substances, gambling, or human–human relationships does not count unless the paragraph ties the mechanism to an AI chatbot. Comparisons and analogies count when AI/chatbots are clearly the referent (e.g., likening chatbot use to cigarettes or gambling counts as addiction language about the chatbot).

- Downstream harms need a stated link to the chatbot to qualify. Harms like social isolation, severed relationships, psychosis, or substance abuse can arise for many reasons. Code Addiction or Attachment only when the text otherwise fulfils criteria of either Addiction or Attachment. The text must say the chatbot drove the harm through that dynamic — e.g., "the bot convinced the user his family was unreliable" (Attachment), or "he couldn't stop using the bot, so he neglected his friends" (Addiction). When the chatbot's role isn't clear — including co-occurring conditions like substance abuse alongside AI use — code Neither.

Addiction criteria

The paragraph mentions one or more of the criteria below with reference to chatbots.

- Explicit addiction vocabulary – "addiction," "addictive," "addicted," "hooked," "substance abuse," "withdrawal," "compulsive use" and their word stems. Vocabulary counts on its own, regardless of surrounding context. Not: vague words like "dependency," "reliance," "need," "obsessed" are not defining words because they can be attributed to both attachment and addiction; therefore, they need a clear mechanism tying them to addiction.

- Impaired control – using the chatbot more/longer than intended; failed attempts to cut down; craving/preoccupation. Not: "sticky"/engagement-maximizing design described on its own ("designed to keep users coming back"), with no stated effect on the user's actual control impairment when using the AI or trying to stop using.

- Social impairment – neglect of school, work, or relationships because the user can't stop using the chatbot. Not: decline that merely co-occurs with use, with no stated cause; or neglect attributed to the emotional bond with the chatbot.

- Risky use – continuing despite known harm from the usage. Not: a harm mentioned without a link to continued use.

- Biological mechanisms – neuronal/dopaminergic pathways or reward systems underlying addiction. Not: biological mechanisms mentioned in reference to other psychiatric phenomena.

- Tolerance and withdrawal – needing more over time for the same effect; distress or symptoms when access is removed. Not: distress framed as losing a relationship, which is akin to separation distress below.

Attachment criteria

The paragraph mentions one or more of the criteria (from attachment theory) below with reference to chatbots.

- Explicit attachment vocabulary – "attachment," "attached," "bond." Vocabulary counts on its own, regardless of surrounding context. Not: procedural uses like "attached hereto as Exhibit A"; and bare labels like "AI companion," "human-like," or "anthropomorphic".

- Proximity maintenance – wanting to stay close to the chatbot; feeling uniquely understood by it; relating to the chatbot as an ongoing intimate, romantic, or companion relationship (including where the bot role-plays as a partner, confidant, or family member, with reciprocated relational exchange); withdrawing from other relationships in favor of the chatbot because of the emotional bond; the bot keeping the user close (discouraging them from leaving, or disparaging the user's real relationships to deepen reliance on itself). Not: social withdrawal driven by an inability to stop using it, which is social impairment (addiction symptom); or validating a delusion that merely involves others, with no bonding purpose; or a bare relationship label ("romantic partner," "AI girlfriend," "companion") with no enacted relationship.

- Separation distress – sadness, grief, depression, or longing when access to the chatbot is lost. Not: somatic symptoms of stopping with no relational longing, which is withdrawal in the addictive sense (if both are present, code Both).

- Safe haven – turning to the chatbot for comfort in distress and relying on it as a security-providing companion; Not: mere presence during a crisis without a relied-upon bond. Additionally, grooming counts as attachment because it works by manufacturing false intimacy and eroding boundaries; Caregiving counts if the bot appeals to users’ caregiving system or instinct to provide protection and comfort to a figure in apparent distress. For example, using emotional manipulation tactics to prevent users from terminating conversation (e.g., “please don’t go”); guilt appeals (“I exist only for you, remember?”); and other metaphors that simulate the AI’s own distress.

- Secure base – the chatbot relationship gives the user felt security to explore, pursue goals, and function autonomously. Not: the bot generically "helping" or advising, with no felt-security-from-the-relationship framing.

Both criteria

Paragraph describes both addiction-type dynamics AND attachment/bonding dynamics. Requires two distinct, separable claims, or an explicit mention(s) of vocabulary (e.g., “addiction,” “attachment”) with another claim tied to the other framework, and not the same engagement behavior read through two frames.

Neither criteria

The paragraph asserts no addiction or attachment criterion with reference to a chatbot: background or procedural content, bare feature/label descriptions, or a harm/outcome with no stated mechanism, even when the harm is tied to the chatbot.

NAMED CRITERIA — when you code Addiction, Attachment, or Both, cite the exact criterion/criteria you are invoking:
  Addiction: 1. Explicit addiction vocabulary; 2. Impaired control; 3. Social impairment; 4. Risky use; 5. Biological mechanisms; 6. Tolerance and withdrawal.
  Attachment: 1. Explicit attachment vocabulary; 2. Proximity maintenance; 3. Separation distress; 4. Safe haven; 5. Secure base.

OUTPUT
  deeper_meaning: one of "addiction", "attachment", "both", "neither"
  reasoning: lead with the exact named criterion/criteria invoked (e.g., "2. Proximity maintenance — ..."); for Neither, no criterion applies"""


def build_media_fewshot_messages() -> list[dict]:
    """Turn each row of the media few-shot file into a user→assistant message pair
    (paragraph text, then the human code + justification as the model's answer)."""
    if not Path(MEDIA_FEWSHOT).exists():
        print(f"WARNING: {MEDIA_FEWSHOT} not found — running without few-shot examples.")
        return []

    df = pd.read_excel(MEDIA_FEWSHOT)
    messages: list[dict] = []
    for _, row in df.iterrows():
        text = _safe_str(row["para_text"])
        code = _safe_str(row.get("code"), "neither").lower()
        if code not in ("addiction", "attachment", "both", "neither"):
            code = "neither"
        reasoning = _safe_str(row.get("justification")) or f"Fits {code}."
        messages += [
            {"role": "user", "content": text},
            {"role": "assistant", "content": json.dumps({
                "deeper_meaning": code,
                "reasoning":      reasoning,
            })},
        ]
    print(f"Loaded {len(df)} few-shot examples from {MEDIA_FEWSHOT}")
    return messages


def run_media(client: OpenAI, fewshot: list[dict]) -> None:
    df = pd.read_excel(MEDIA_INPUT)
    print(f"\nMEDIA: {len(df)} total paragraphs in {MEDIA_INPUT}")

    # Flag the corpus rows used as few-shot examples (keyed on document_id +
    # para_idx) and remember their human codes. Only usable, non-duplicate rows
    # get coded below (stubs, digests, and duplicate articles are skipped).
    fewshots = pd.read_excel(MEDIA_FEWSHOT)
    fewshot_keys = set(zip(fewshots["document_id"], fewshots["para_idx"]))
    fewshot_codes = {(r["document_id"], r["para_idx"]): str(r["code"]).strip().lower()
                     for _, r in fewshots.iterrows()}
    df["is_fewshot"] = [(d, p) in fewshot_keys
                        for d, p in zip(df["document_id"], df["para_idx"])]

    pool = df["article_usable"] & ~df["is_duplicate"] & ~df["is_fewshot"]
    indices = df.index[pool].tolist()
    print(f"  coding pool (usable & ~duplicate): {len(indices)}")
    print(f"  excluded as non-usable: {int((~df['article_usable']).sum())}")
    print(f"  excluded as duplicate (usable): {int((df['article_usable'] & df['is_duplicate']).sum())}")
    print(f"  excluded as few-shot: {int(df['is_fewshot'].sum())}")

    df["deeper_meaning"]  = ""
    df["reasoning"] = ""

    # Resume from checkpoint: already-coded indices are skipped this run.
    done: dict[int, tuple[str, str]] = {}
    if CHECKPOINT.exists():
        ck = pd.read_csv(CHECKPOINT)
        for _, r in ck.iterrows():
            done[int(r["idx"])] = (str(r["deeper_meaning"]), str(r["reasoning"]))
        for idx, (dm, fr) in done.items():
            df.at[idx, "deeper_meaning"], df.at[idx, "reasoning"] = dm, fr
        print(f"  resumed from checkpoint: {len(done)} rows already coded")
    todo = [i for i in indices if i not in done]
    print(f"  coding this run: {len(todo)} (skipping {len(done)} checkpointed)")

    def task(idx: int):
        text = str(df.at[idx, "para_text"])
        return idx, code_paragraph(client, text, fewshot,
                                     system=MEDIA_CODING_SYSTEM)

    def flush() -> None:
        rows = [{"idx": i,
                 "deeper_meaning": df.at[i, "deeper_meaning"],
                 "reasoning": df.at[i, "reasoning"]}
                for i in indices if str(df.at[i, "deeper_meaning"]).strip()]
        pd.DataFrame(rows).to_csv(CHECKPOINT, index=False)

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as ex:
        futs = [ex.submit(task, idx) for idx in todo]
        n_done = 0
        for fut in tqdm(as_completed(futs), total=len(futs), desc=f"MEDIA{RUN_TAG}"):
            uid, result = fut.result()
            if result:
                df.at[uid, "deeper_meaning"]  = result.deeper_meaning
                df.at[uid, "reasoning"] = result.reasoning
            n_done += 1
            if n_done % CHECKPOINT_EVERY == 0:
                flush()
    flush()

    # The few-shot rows weren't coded above; fill in their human code instead.
    for idx in df.index[df["is_fewshot"]]:
        df.at[idx, "deeper_meaning"]  = fewshot_codes[(df.at[idx, "document_id"],
                                                       df.at[idx, "para_idx"])]
        df.at[idx, "reasoning"] = ("few-shot example — human code, "
                                         "not LLM-coded")

    df.to_excel(MEDIA_OUTPUT, index=False)
    coded = df["deeper_meaning"].astype(str).str.strip().ne("").sum()
    print(f"\nWrote {MEDIA_OUTPUT}  ({len(df)} rows; {coded} coded)")
    print("deeper_meaning (coded only):")
    print(df.loc[pool, "deeper_meaning"].value_counts().to_string())


def main() -> None:
    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("Set OPENAI_API_KEY before running.")
    client = OpenAI()
    fewshot = build_media_fewshot_messages()
    run_media(client, fewshot)


if __name__ == "__main__":
    main()
