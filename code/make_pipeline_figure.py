#!/usr/bin/env python3
"""
Render figures/figure0_pipeline.png: the text-analysis workflow schematic.

Layout mirrors the manuscript's Figure 1 — a vertical spine of four stages
(Preparation, Surface, Deeper, Output) with a left rail of stage labels and two
side boxes branching right (the dictionary result and the reliability check).

Corpus counts are read live from the paragraph/LLM files. The reliability
numbers are manually maintained constants below — update them when the
validation sample is re-scored. All text is written in plain language for a
reader with no project context (no internal shorthand, no "gold standard").
"""
from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import pandas as pd

ROOT     = Path(__file__).resolve().parent.parent
FIG_DIR  = ROOT / "figures"; FIG_DIR.mkdir(exist_ok=True)
DATA_DIR = ROOT / "modified_data"
OUT_DIR  = ROOT / "output"

# ── live corpus numbers ────────────────────────────────────────────────────
legal_para = pd.read_excel(DATA_DIR / "legal_paragraphs.xlsx")
media_para = pd.read_excel(DATA_DIR / "media_paragraphs.xlsx")
media_uu   = media_para[media_para["article_usable"] & ~media_para["is_duplicate"]]

L_PARAS = len(legal_para)
L_CASES = legal_para["case"].nunique()
M_PARAS = len(media_uu)


def _surf(df):
    vc = df["surface_meaning"].value_counts()
    return {c: int(vc.get(c, 0)) for c in ("addiction", "attachment", "both", "neither")}


L = _surf(legal_para)
M = _surf(media_uu)

# ── reliability numbers (manually maintained; update when re-scored) ─────────
# Validation sample stratified by AI code, N = 150 per corpus, two coders
# (blind), reconciled to a single agreed code, then compared to the AI.
IRR_N            = 150
KAPPA_HUMAN_AI_L = 0.79   # Cohen's kappa, agreed human code vs AI
KAPPA_HUMAN_AI_M = 0.77
RAW_HUMAN_AI_L   = 85     # % raw agreement
RAW_HUMAN_AI_M   = 83
KAPPA_REPEAT_L   = 0.90   # AI vs itself across two independent runs
KAPPA_REPEAT_M   = 0.87

# ── styling ────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":     "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
})
SPINE_FILL  = "#f4f6fb"
SPINE_EDGE  = "#3a4a6b"
RAIL_FILL   = "#3a4a6b"
SIDE_FILL   = "#eef1f7"
SIDE_EDGE   = "#7385a8"
TXT_DARK    = "#1f2a3d"

H_HEAD = 13   # box header
H_BODY = 11   # box body text
H_RAIL = 13   # left-rail stage label
H_SIDE = 10   # side-box text

ARROW = r"$\rightarrow$"   # mathtext arrow (Helvetica lacks the unicode glyph)
LINE_DY = 0.34             # vertical spacing between body lines

fig, ax = plt.subplots(figsize=(13, 9.5))
ax.set_xlim(0, 13); ax.set_ylim(0, 9.5); ax.axis("off")

# geometry
RAIL_X, RAIL_W = 0.25, 1.15
SPINE_X, SPINE_W = 1.75, 6.15
SIDE_X, SIDE_W = 8.75, 4.10


def _box(x, w, top, header, lines, header_size, body_size, edge, lw=1.3):
    """Draw a rounded box whose height fits header + lines; return (bottom, y_center)."""
    h = 0.52 + len(lines) * LINE_DY + 0.16
    ax.add_patch(FancyBboxPatch(
        (x, top - h), w, h, boxstyle="round,pad=0.03,rounding_size=0.10",
        linewidth=lw, edgecolor=edge, facecolor=SPINE_FILL if edge == SPINE_EDGE else SIDE_FILL))
    ax.text(x + 0.28, top - 0.34, header, ha="left", va="center",
            fontsize=header_size, color=TXT_DARK, fontweight="bold")
    yb = top - 0.80
    for ln in lines:
        ax.text(x + 0.28, yb, ln, ha="left", va="center",
                fontsize=body_size, color="#222")
        yb -= LINE_DY
    return top - h, top - h / 2


# ── spine: four stacked stage boxes ─────────────────────────────────────────
stages = [
    ("Preparation", "Data preparation", [
        f"Legal: {L_CASES} complaints {ARROW} {L_PARAS:,} numbered paragraphs.",
        f"Media: 828 articles {ARROW} 578 unique {ARROW} {M_PARAS:,} paragraphs.",
        "Procedural “attached as Exhibit” uses excluded.",
    ]),
    ("Surface\nanalysis", "Surface-level analysis", [
        "Dictionary tagging on the word stems of",
        "“addiction” and “attachment.”",
        "Each paragraph labeled addiction, attachment,",
        "both, or neither.",
    ]),
    ("Deeper\nanalysis", "Deeper analysis", [
        "GPT-5.4 four-class classifier (high reasoning),",
        "guided by a formal coding manual, one per corpus.",
        f"Calibrated with {IRR_N} example paragraphs per corpus.",
    ]),
    ("Output", "Final labeled corpus", [
        f"Legal: {L_PARAS:,} paragraphs.   Media: {M_PARAS:,} paragraphs.",
        "Each labeled addiction, attachment, both, or neither.",
    ]),
]

top = 8.80
GAP = 0.34
centers = []
for rail, head, body in stages:
    bottom, yc = _box(SPINE_X, SPINE_W, top, head, body, H_HEAD, H_BODY, SPINE_EDGE)
    centers.append((yc, top, bottom))
    # left-rail stage chip
    ax.add_patch(FancyBboxPatch(
        (RAIL_X, yc - 0.34), RAIL_W, 0.68,
        boxstyle="round,pad=0.02,rounding_size=0.10", linewidth=0, facecolor=RAIL_FILL))
    ax.text(RAIL_X + RAIL_W / 2, yc, rail, ha="center", va="center",
            fontsize=H_RAIL, color="white", fontweight="bold", linespacing=1.1)
    top = bottom - GAP

# downward arrows between consecutive spine boxes
xmid = SPINE_X + SPINE_W / 2
for i in range(len(stages) - 1):
    ax.add_patch(FancyArrowPatch(
        (xmid, centers[i][2] - 0.02), (xmid, centers[i + 1][1] + 0.02),
        arrowstyle="-|>", mutation_scale=20, linewidth=2.0, color=SPINE_EDGE))

# ── two side boxes branching right, at fixed non-overlapping positions ──────
sb_bottom, sr_yc = _box(SIDE_X, SIDE_W, 7.55, "Surface (dictionary) result", [
    f"Legal:  {L['addiction']} addiction / {L['attachment']} attachment /",
    f"           {L['both']} both / {L['neither']:,} neither.",
    f"Media:  {M['addiction']} addiction / {M['attachment']} attachment /",
    f"           {M['both']} both / {M['neither']:,} neither.",
], H_HEAD - 1, H_SIDE, SIDE_EDGE, lw=1.2)

_, rl_yc = _box(SIDE_X, SIDE_W, 4.95, "Reliability check", [
    f"A separate sample of {IRR_N} paragraphs per corpus.",
    "Two coders labeled each one independently,",
    "then agreed a single code per paragraph.",
    f"Agreement with the AI:  κ = {KAPPA_HUMAN_AI_L:.2f} legal ({RAW_HUMAN_AI_L}%),",
    f"           κ = {KAPPA_HUMAN_AI_M:.2f} media ({RAW_HUMAN_AI_M}%).",
    f"AI vs. itself, two runs:  κ = {KAPPA_REPEAT_L:.2f} / {KAPPA_REPEAT_M:.2f}.",
], H_HEAD - 1, H_SIDE, SIDE_EDGE, lw=1.2)

# connectors: Surface stage → surface result; Deeper stage → reliability
ax.add_patch(FancyArrowPatch((SPINE_X + SPINE_W + 0.02, centers[1][0]),
             (SIDE_X - 0.02, sr_yc), arrowstyle="-|>", mutation_scale=16,
             linewidth=1.6, color=SIDE_EDGE))
ax.add_patch(FancyArrowPatch((SPINE_X + SPINE_W + 0.02, centers[2][0]),
             (SIDE_X - 0.02, rl_yc), arrowstyle="-|>", mutation_scale=16,
             linewidth=1.6, color=SIDE_EDGE))

# title
ax.text(0.25, 9.20, "Figure 1. Text analysis workflow",
        ha="left", va="center", fontsize=17, fontweight="bold", color=TXT_DARK)

plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
out = FIG_DIR / "figure0_pipeline.png"
plt.savefig(out, dpi=300, bbox_inches="tight")
plt.close()
print(f"wrote {out}")
