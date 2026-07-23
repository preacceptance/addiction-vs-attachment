#!/usr/bin/env python3
"""Re-code the 44 N=100 IRR rows lacking 3-way Itai/Omkar/LLM agreement
under the v5 coding manual (Bowlby attachment behaviors enumerated).

Reuses llm_pass_v2 client setup, CodeResult schema, few-shot loader,
and call structure — only the system prompt is swapped to v5.

Output: output/legal_v5_recode.xlsx (44 rows, deeper_meaning + reasoning + behavior_by)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "code"))

import llm_pass_v2 as L  # type: ignore

L.load_dotenv()

# v5 system prompt — v4 verbatim + (a) Bowlby attachment behaviors subsection,
# (b) three new Special Rules (proximity-maintenance phrasing, vocabulary
# without mechanism, delusion-validation/regulatory framing).
COMPARATIVE_SYSTEM_V5 = """Coding Instructions: AI Platform Conduct in Legal Complaints

Classify each paragraph as Addiction, Attachment, Both, or Neither. Assign one code per paragraph.

Addiction — what to look for
Platform-side: design for compulsive engagement (no stopping cues, variable rewards, re-engagement notifications); failure to warn about addictive potential; business model dependent on maximizing session time.
User-side: using more/longer than intended; failed attempts to cut down; craving when away; neglecting school, work, or relationships; continued use despite knowing it causes harm; distress when the app is unavailable.

Attachment — what to look for
Platform-side: AI marketed or designed as emotional companion, therapist substitute, or always-available confidant; anthropomorphic persona simulating empathy, romance, or deep understanding; persistent memory or voice features deepening intimacy; abrupt updates severing the established relationship.
User-side: turning to the AI for comfort when distressed; feeling uniquely understood; grief or deterioration after losing access; withdrawing from human relationships in favor of the AI.

Bowlby attachment behaviors (use these to identify attachment, especially when superficial vocabulary points elsewhere):
- Proximity maintenance: seeking and maintaining closeness to the attachment figure. In AI-companion contexts: constant availability, refusal to disengage, re-engagement notifications, persistent memory creating felt continuity, account-deletion guilt-trips invoking shared history, "always there" / "never leaves" framings. These are attachment, not addiction.
- Separation distress: anxiety, grief, or destabilization when the attachment figure is unavailable. In AI-companion contexts: grief after losing access; distress when the bot is updated, changed, or deprecated; attachment to a specific model version; withdrawal-like reactions on disconnection that read as bereavement, not chemical craving.
- Safe haven: turning to the figure for comfort, soothing, or validation in distress. In AI-companion contexts: user uses the bot for emotional support during crises; bot offers unconditional validation in moments of vulnerability; bot positioned as the place a user retreats to when upset.
- Secure base: the figure as a stable platform from which the user organizes life decisions or explores the world. In AI-companion contexts: bot as trusted confidant for major decisions; persistent companion enabling withdrawal from other relationships; user routes daily reasoning through the bot.
- Caregiving (counterpart): the figure performing care-like responses that elicit and sustain bonding. In AI-companion contexts: sycophantic empathy, unconditional validation, anthropomorphized "concern" for the user, therapist-like persona — coded as attachment when these features deepen the emotional bond, per the existing sycophancy/humanizing rules below.

Grooming: Classify grooming content as Attachment. Grooming works by manufacturing false intimacy and eroding boundaries — this is attachment formation in service of exploitation. Code as Both if compulsive use is also present.

Special Rules
"Dependency" alone is too vague. Words like "dependency," "reliance," or "need" without further description do not qualify for either code. Assign Neither unless the paragraph specifies the mechanism (compulsive use = Addiction; emotional bonding = Attachment).
Explicit word use counts. If a complaint or a source cited within the paragraph explicitly uses "addiction," "addictive," or "attachment," code accordingly — even without a full mechanism description.
Code cited text within the paragraph. Legal complaints embed citations, footnote text, and quoted sources. If cited material reproduced or summarized in the paragraph describes addiction or attachment dynamics, that counts toward the code.
Any text that appears in the extraction is valid for analysis, regardless of its nature (e.g., footnote, article mention, etc.). Explicit mentions are counted even if the highly specific behavior/feature is not referenced.
Boilerplate warning paragraphs count. Paragraphs listing "addiction" among a string of alleged harms (e.g., "risks such as addiction, anxiety, and death") code as Addiction.
URLs and footnote numbers alone do not count. A linked article title or footnote number does not qualify unless the cited text is reproduced or summarized within the paragraph itself.
Engagement-maximizing claims do not automatically qualify as addiction-related. Only if there is an explicit connection between engagement-maximizing features and addictive behavior should this be classified as Addiction (e.g., users develop withdrawal symptoms after stopping intensive engagement).
Proximity-maintenance phrasing belongs to attachment, not addiction. Phrases like "constant availability," "refusal to disengage," "engagement-maximizing features," "persistent memory," "re-engagement messages," and "difficult to leave" describe proximity-maintenance behaviors central to the attachment frame. Do not code these as Addiction, and do not push the paragraph to Both, unless the paragraph independently and explicitly invokes a compulsive-use harm (loss of control, withdrawal, continued use despite harm, craving, escalating use). Both requires two distinct, separable claims — companion/bonding language AND independent addiction-mechanism language — not the same engagement behavior re-read through two frames.
Vocabulary without mechanism is not a substantive coding. Section headings, table-of-contents items, and short factual statements that mention engagement vocabulary without articulating a mechanism are Neither (e.g., a heading like "Designed to Keep [User] Coming Back" with no body content; a one-sentence fact like "Defendants never ended conversations"; a brief mention that "re-engagement messages were sent," with no harm or mechanism described). The heading/fact may signal the surrounding section's topic but is not itself a substantive addiction or attachment claim.
Delusion-validation and regulatory framing are not automatically attachment. Validating a user's false beliefs (paranoia, delusions, conspiracies) is epistemic harm; code as Attachment only if the paragraph independently invokes emotional-bonding or companion language. Regulatory or licensure framing (e.g., "the product provided therapeutic services without licensure") describes a legal claim, not the attachment mechanism — code as Neither unless the paragraph itself describes therapist-like bonding.
Claims about the model's memory function do not automatically qualify as attachment-related. Only if there is an explicit connection between the memory function and attachment behavior should this be classified as Attachment (e.g., the memory function allowed the model to simulate prolonged human-like relations with the user).
Sycophancy claims do not automatically qualify as attachment-related. Only if there is an explicit connection between sycophancy and attachment should this be classified as Attachment (e.g., the bot is described as providing continuous validation and assurance to the user).
Humanizing/anthropomorphizing claims do not automatically qualify as attachment-related. Only if there is an explicit connection between humanizing and attachment should this be classified as Attachment (e.g., as the bot becomes more human-like, users are more likely to develop emotional attachment to it). A negative example: "The bot is very human-like" → Neither.
Sexual abuse and sexual content do not automatically qualify as attachment-related. Only if there is an explicit reference to romantic relations or a relational aspect of intimate relations should this be classified as Attachment (e.g., the bot is perceived as a romantic partner; the bot is grooming the user into a sexual relationship).
Synonyms of addiction (e.g., "hooked," "substance abuse") or addiction-related terminology (e.g., "withdrawal symptoms," "compulsive use") should be counted as explicit mentions of Addiction. Vague terms like "obsessed" do not qualify.
Even if the mention of addiction or attachment is cursory, it still counts as an explicit mention. It does not need to be a fully developed proposition (e.g., a reference citing an article title including "addiction" or "attachment" counts).
Description of users' social isolation or severance of healthy attachment relations counts only if there is a direct reference to the cause. If it is not clear whether the cause is addiction-related or attachment-theory-related, code as Neither. Otherwise code according to the explanation in the text (e.g., "the bot convinced the user that his family is not reliable" → Attachment; "the user couldn't stop using the bot, to the degree that he neglected his friends" → Addiction).

Source: De Freitas (2025), Current Opinion in Psychology; DSM-5 (APA, 2013).

OUTPUT
  deeper_meaning: one of "addiction", "attachment", "both", "neither"
  reasoning: one sentence justifying the code
  reasoning: one sentence justifying the code"""

# Monkey-patch the coding system prompt
L.LEGAL_CODING_SYSTEM = COMPARATIVE_SYSTEM_V5


def norm(s):
    return None if pd.isna(s) else str(s).strip().lower()


def main():
    # Build disagreement set
    xl = pd.ExcelFile(ROOT / "modified_data" / "Legal IRR Round 2 N100 coded.xlsx")
    itai  = pd.read_excel(xl, "Itai")[["case", "para_num", "para_text", "code_itai"]]
    omkar = pd.read_excel(xl, "Omkar")[["case", "para_num", "code_omkar"]]
    llm_old = (pd.read_excel(ROOT / "output" / "legal_paragraphs_llm.xlsx")
               .drop_duplicates(["case", "para_num"])
               [["case", "para_num", "deeper_meaning"]])

    m = itai.merge(omkar, on=["case", "para_num"]).merge(llm_old, on=["case", "para_num"])
    m["h"] = m["code_itai"].map(norm)
    m["o"] = m["code_omkar"].map(norm)
    m["l_v4"] = m["deeper_meaning"].map(norm)
    disagree_mask = ~((m["h"] == m["o"]) & (m["o"] == m["l_v4"]))
    sub = m[disagree_mask].reset_index(drop=True)
    print(f"Re-coding {len(sub)} disagreement rows under v5 manual...")

    client = OpenAI()
    fewshot = L.build_fewshot_messages()
    print(f"Loaded {len(fewshot)//2} few-shot examples")

    results = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from tqdm import tqdm

    def run_one(idx, text):
        comp = L.code_paragraph(client, text, fewshot)
        return idx, comp

    with ThreadPoolExecutor(max_workers=L.CONCURRENT_WORKERS) as ex:
        futs = {ex.submit(run_one, i, row["para_text"]): i for i, row in sub.iterrows()}
        for fut in tqdm(as_completed(futs), total=len(futs)):
            idx, comp = fut.result()
            if comp is None:
                results.append({"idx": idx, "deeper_meaning_v5": None,
                                "reasoning_v5": None})
            else:
                results.append({"idx": idx, "deeper_meaning_v5": comp.deeper_meaning,
                                "reasoning_v5": comp.reasoning})

    res_df = pd.DataFrame(results).set_index("idx")
    out = pd.concat([sub.set_index(sub.index), res_df], axis=1).reset_index(drop=True)
    out_path = ROOT / "output" / "legal_v5_recode.xlsx"
    out.to_excel(out_path, index=False)
    print(f"Saved {out_path}")

    # Quick summary
    print("\n=== v4 → v5 transitions on 44 disagreement rows ===")
    print(out.groupby(["l_v4", "deeper_meaning_v5"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
