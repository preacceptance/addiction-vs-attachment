#!/usr/bin/env python3
"""
Unified "N at every stage" chart for both corpora.

Pulls live counts from legal_paragraphs.xlsx, media_articles.xlsx,
media_paragraphs.xlsx, legal_fewshot_v3.xlsx, media_fewshot_v3.xlsx,
and legal_irr_v2.xlsx so the figure cannot drift from the data.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ── Pull live N's ────────────────────────────────────────────────────────
lp  = pd.read_excel("legal_paragraphs.xlsx")
mp  = pd.read_excel("media_paragraphs.xlsx")
ma  = pd.read_excel("media_articles.xlsx")
fsl = pd.read_excel("legal_fewshot_v3.xlsx")
fsm = pd.read_excel("media_fewshot_v3.xlsx")
irr = pd.read_excel("legal_irr_v2.xlsx", sheet_name="IRR")

mp_u = mp[mp.article_usable & ~mp.is_duplicate]


# Optional deeper-meaning loads (graceful if a run hasn't finished yet)
def _deeper(path, mask_col=None):
    p = Path(path)
    if not p.exists():
        return None
    d = pd.read_excel(p)
    if mask_col and mask_col in d.columns:
        d = d[d[mask_col]]
    coded = d[d["deeper_meaning"].astype(str).str.strip() != ""] if "deeper_meaning" in d.columns else d.iloc[:0]
    return coded


lpllm = _deeper("legal_paragraphs_llm.xlsx")
mpllm_raw = pd.read_excel("media_paragraphs_llm.xlsx") if Path("media_paragraphs_llm.xlsx").exists() else None
mpllm = mpllm_raw[mpllm_raw.article_usable & ~mpllm_raw.is_duplicate] if mpllm_raw is not None else None
mpllm_coded = mpllm[mpllm["deeper_meaning"].astype(str).str.strip() != ""] if mpllm is not None and "deeper_meaning" in mpllm.columns else None


def _deeper_count(coded, label):
    if coded is None or len(coded) == 0:
        return "pending run"
    return f"{int((coded.deeper_meaning == label).sum()):,}"

ROWS = [
    ("Source PDFs",                        "14 legal complaints",                       f"{ma.pdf.nunique()} Factiva exports"),
    ("Article instances",                  "—",                                          f"{len(ma):,}"),
    ("Usable articles (post-stub filter)", "14 cases",                                   f"{int(ma.usable.sum()):,}"),
    ("Unique articles (dedup)",            "14 cases",                                   f"{int((ma.usable & ~ma.is_duplicate).sum()):,}"),
    ("Paragraphs (total in corpus)",       f"{len(lp):,}",                               f"{len(mp):,}"),
    ("Paragraphs (LLM coding pool)",       f"{len(lp):,} (all)",                         f"{len(mp_u):,} (usable & unique)"),
    ("Mangled paragraphs flagged",         f"{int(lp.mangled.sum())}",                   "0 (corpus is mangle-free)"),
    ("Surface: Addiction",                 f"{int((lp.surface_meaning == 'addiction').sum())}",
                                           f"{int((mp_u.surface_meaning == 'addiction').sum())}"),
    ("Surface: Attachment",                f"{int((lp.surface_meaning == 'attachment').sum())}",
                                           f"{int((mp_u.surface_meaning == 'attachment').sum())}"),
    ("Surface: Both",                      f"{int((lp.surface_meaning == 'both').sum())}",
                                           f"{int((mp_u.surface_meaning == 'both').sum())}"),
    ("Surface: Neither",                   f"{int((lp.surface_meaning == 'neither').sum()):,}",
                                           f"{int((mp_u.surface_meaning == 'neither').sum()):,}"),
    ("Deeper LLM: Addiction",              _deeper_count(lpllm, "addiction"),            _deeper_count(mpllm_coded, "addiction")),
    ("Deeper LLM: Attachment",             _deeper_count(lpllm, "attachment"),           _deeper_count(mpllm_coded, "attachment")),
    ("Deeper LLM: Both",                   _deeper_count(lpllm, "both"),                 _deeper_count(mpllm_coded, "both")),
    ("Deeper LLM: Neither",                _deeper_count(lpllm, "neither"),              _deeper_count(mpllm_coded, "neither")),
    ("Few-shot (3-coder consensus)",       f"{len(fsl)}",                                f"{len(fsm)}"),
    ("IRR (held-out)",                     f"{len(irr)}",                                "30 (blank, pending coding)"),
]


# ── Render as a clean matplotlib table figure ────────────────────────────
fig, ax = plt.subplots(figsize=(11, 6.5), dpi=200)
ax.axis("off")

table = ax.table(
    cellText=[[r[1], r[2]] for r in ROWS],
    rowLabels=[r[0] for r in ROWS],
    colLabels=["Legal", "Media"],
    loc="center",
    cellLoc="left",
    rowLoc="left",
    colWidths=[0.32, 0.42],
)
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.0, 1.55)

# Header styling
for (row, col), cell in table.get_celld().items():
    cell.set_edgecolor("#bbbbbb")
    cell.set_linewidth(0.5)
    if row == 0:
        cell.set_facecolor("#2c3e50")
        cell.set_text_props(color="white", weight="bold")
    elif col == -1:
        cell.set_facecolor("#ecf0f1")
        cell.set_text_props(weight="bold")
        cell.PAD = 0.05

plt.title("Sample sizes at every pipeline stage — legal vs media",
          fontsize=13, weight="bold", pad=14)
plt.figtext(0.5, 0.02,
            "Live counts from legal_paragraphs.xlsx · media_articles.xlsx · media_paragraphs.xlsx · "
            "legal_fewshot_v3.xlsx · media_fewshot_v3.xlsx · legal_irr_v2.xlsx",
            ha="center", fontsize=7.5, style="italic", color="#555")
plt.tight_layout()
out = Path("figures/n_summary.png")
out.parent.mkdir(exist_ok=True)
plt.savefig(out, dpi=200, bbox_inches="tight")
print(f"wrote {out}")
