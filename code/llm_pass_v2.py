#!/usr/bin/env python3
"""Classify each paragraph of the legal-complaint corpus as addiction, attachment,
both, or neither — one LLM call per paragraph, returning the code plus a short
reasoning.

Input:  modified_data/legal_paragraphs.xlsx   (one row per paragraph)
Output: output/legal_paragraphs_llm.xlsx      (same rows + deeper_meaning, reasoning)

The request sent to the model is the coding manual (LEGAL_CODING_SYSTEM, generated
from the manual .docx by dev/bake_manuals.py — edit the docx, not this file) plus a
set of hand-coded few-shot examples (FEW_SHOT_FILE). The example paragraphs are
skipped during coding (using them as targets would be circular) and instead keep
their human code in the output. Model: gpt-5.4, high reasoning effort.
Requires OPENAI_API_KEY (in the shell or a .env file at the project root).
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from openai import OpenAI
from pydantic import BaseModel
from tqdm import tqdm


ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and val and val != "PASTE_YOUR_KEY_HERE":
            os.environ.setdefault(key, val)


load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────
MODEL              = "gpt-5.4"
REASONING_EFFORT   = "high"
CONCURRENT_WORKERS = 20
MAX_RETRIES        = 3

# Hand-coded few-shot examples shown to the model (paragraph text + its code + a
# justification). Loaded at runtime. These paragraphs are excluded from coding and
# keep their human code in the output.
FEW_SHOT_FILE = ROOT / "modified_data" / "legal_fewshot_v7.xlsx"

LEGAL_INPUT         = ROOT / "modified_data" / "legal_paragraphs.xlsx"
LEGAL_OUTPUT        = ROOT / "output" / "legal_paragraphs_llm.xlsx"


# ── Output schema ───────────────────

class CodeResult(BaseModel):
    """The model's answer for one paragraph: the category and a one-line rationale."""
    deeper_meaning: Literal["addiction", "attachment", "both", "neither"]
    reasoning: str


# ── System prompts ───────────────────────────────────────────────────────

# The coding manual, sent as the system prompt. Auto-generated from the manual
# .docx by dev/bake_manuals.py — do NOT edit the text here; edit the .docx and
# re-run the baker.
LEGAL_CODING_SYSTEM = """Coding Instructions: AI Platform Conduct in Legal Complaints

You will read paragraphs from legal complaints (lawsuits) against chatbot companies. Your job is to characterize the phenomenon described in each paragraph. Classify each paragraph as Addiction (based on DSM criteria), Attachment (based on attachment theory), Both, or Neither. Assign one code per paragraph.

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


# ── Few-shot builder ─────────────────────────────────────────────────────

def _safe_str(val, fallback: str = "") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return fallback
    return str(val).strip()


def build_fewshot_messages() -> list[dict]:
    """Turn each row of the few-shot file into a user→assistant message pair
    (paragraph text, then the human code + justification as the model's answer).
    Returns one flat list of message dicts to prepend to every request."""
    if not Path(FEW_SHOT_FILE).exists():
        print(f"WARNING: {FEW_SHOT_FILE} not found — running without few-shot examples.")
        return []

    df = pd.read_excel(FEW_SHOT_FILE)
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

    print(f"Loaded {len(df)} few-shot examples from {FEW_SHOT_FILE}")
    return messages


# ── API calls ────────────────────────────────────────────────────────────

def code_paragraph(client: OpenAI, text: str,
                     fewshot: list[dict],
                     system: str = LEGAL_CODING_SYSTEM) -> Optional[CodeResult]:
    messages = [{"role": "system", "content": system}]
    messages += fewshot
    messages.append({"role": "user", "content": text})
    for attempt in range(MAX_RETRIES):
        try:
            kwargs = dict(model=MODEL, messages=messages,
                          response_format=CodeResult)
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


def run_legal(client: OpenAI, fewshot: list[dict]) -> None:
    df = pd.read_excel(LEGAL_INPUT)

    # Flag the corpus rows that are used as few-shot examples (keyed on
    # case + para_seq) and remember their human codes.
    fewshots = pd.read_excel(FEW_SHOT_FILE)
    fewshot_keys = set(zip(fewshots["case"], fewshots["para_seq"]))
    fewshot_codes = {(r["case"], r["para_seq"]): str(r["code"]).strip().lower()
                     for _, r in fewshots.iterrows()}
    df["is_fewshot"] = [(c, p) in fewshot_keys
                             for c, p in zip(df["case"], df["para_seq"])]
    assert df["is_fewshot"].sum() == len(fewshots), \
        "few-shot rows did not all match the corpus on (case, para_seq)"

    # Code every paragraph except the few-shot examples (coding them would be
    # circular — the model was shown their answers). Those rows keep their human
    # code, filled in further below.
    indices = df.index[~df["is_fewshot"]].tolist()
    print(f"\nLEGAL: {len(indices)} paragraphs selected for coding "
          f"({df['is_fewshot'].sum()} few-shot rows excluded)")
    print(f"  addiction={( df['has_addict'] & ~df['has_attach']).sum()}  "
          f"attachment={(~df['has_addict'] &  df['has_attach']).sum()}  "
          f"both={(df['has_addict'] & df['has_attach']).sum()}  "
          f"neither={(~df['has_addict'] & ~df['has_attach']).sum()}")

    df["surface_meaning"]          = ""
    df["deeper_meaning"]  = ""
    df["reasoning"] = ""

    df.loc[ df["has_addict"] & ~df["has_attach"], "surface_meaning"] = "addiction"
    df.loc[~df["has_addict"] &  df["has_attach"], "surface_meaning"] = "attachment"
    df.loc[ df["has_addict"] &  df["has_attach"], "surface_meaning"] = "both"
    df.loc[~df["has_addict"] & ~df["has_attach"], "surface_meaning"] = "neither"

    results: dict[int, CodeResult] = {}

    def task(idx: int):
        text = str(df.at[idx, "para_text"])
        return idx, code_paragraph(client, text, fewshot)

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as ex:
        futs = [ex.submit(task, idx) for idx in indices]
        for fut in tqdm(as_completed(futs), total=len(futs), desc="LEGAL"):
            uid, result = fut.result()
            results[uid] = result

    for idx, result in results.items():
        if result:
            df.at[idx, "deeper_meaning"]  = result.deeper_meaning
            df.at[idx, "reasoning"] = result.reasoning

    # The few-shot rows weren't coded above; fill in their human code instead.
    for idx in df.index[df["is_fewshot"]]:
        df.at[idx, "deeper_meaning"]  = fewshot_codes[(df.at[idx, "case"],
                                                       df.at[idx, "para_seq"])]
        df.at[idx, "reasoning"] = "few-shot example — human code, not LLM-coded"

    df.to_excel(LEGAL_OUTPUT, index=False)
    coded_n = (df["deeper_meaning"] != "").sum()
    print(f"Wrote {LEGAL_OUTPUT}  ({len(df)} rows, {coded_n} coded)")
    _summarise_legal(df)


def _summarise_legal(df: pd.DataFrame) -> None:
    coded = df[df["deeper_meaning"] != ""].copy()
    print(f"\nLEGAL SUMMARY ({len(coded)} paragraphs coded)")
    print(f"  Overall deeper_meaning: " +
          "  ".join(f"{k}={v}" for k, v in coded["deeper_meaning"].value_counts().items()))
    for subset in ["addiction", "attachment", "both", "neither"]:
        sub = coded[coded["surface_meaning"] == subset]
        n = len(sub)
        if n == 0:
            continue
        frames = sub["deeper_meaning"].value_counts()
        print(f"\n  {subset} (n={n})")
        print(f"    deeper_meaning: " +
              "  ".join(f"{k}={v}" for k, v in frames.items()))


# ── Entry point ──────────────────────────────────────────────────────────

def main() -> None:
    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("Set OPENAI_API_KEY before running.")
    client = OpenAI()
    # Build the few-shot examples once, then code the whole corpus.
    fewshot = build_fewshot_messages()
    run_legal(client, fewshot)


if __name__ == "__main__":
    main()
