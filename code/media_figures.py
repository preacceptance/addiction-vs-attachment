#!/usr/bin/env python3
"""
Render all media-corpus figures from media_paragraphs.xlsx (surface) and
media_paragraphs_llm.xlsx (deeper LLM coding); outputs to figures/.

Parallels legal_figures.py (shared palette/helpers via figures_common). All analyses
restricted to unique-usable paragraphs (article_usable & ~is_duplicate).
"""

from pathlib import Path
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from figures_common import (
    FIG_DIR, OUTPUT_DIR, DATA_DIR,
    ADDICT, ATTACH, BOTH, NEITHER,
    CODE_COLORS,
    USER_C, CHATBOT_C, BOTH_BC, UNCLEAR_C,
    SUBSET_LABEL, SUBSET_ORDER,
    COMPOSITE_LABEL_SCALE, COMPOSITE_NUMBER_SCALE, COMPOSITE_INBAR_MIN_PCT,
    COMPOSITE_AXISTITLE_SCALE, PANEL_C_COMPACT, PANEL_C_MIN_SEG_PCT,
    _barh_stack, _ensure_mentions, _deeper_meaning_stack, _deeper_meaning_stack_compact,
    _title_with_subtitle, _fig_note,
    deeper_meaning_totals, surface_and_deeper_totals,
)

MEDIA_PARA = DATA_DIR / "media_paragraphs.xlsx"
MEDIA_LLM  = OUTPUT_DIR / "media_paragraphs_llm.xlsx"


# Restrict to unique-usable paragraphs (drops unusable articles + cross-search dupes).
def _unique_usable(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["article_usable"] & ~df["is_duplicate"]].copy()


# ─────────────────────────────────────────────────────────────────────────
# Manuscript Figure
# ─────────────────────────────────────────────────────────────────────────
# Manuscript Fig 2: surface vs. deeper totals + per-surface-subset deeper breakdown.
def figure2_media_composite(media_para, media_llm):
    """Figure 2: (a) surface totals | (b) deeper totals | (c) subset breakdown."""
    para = _unique_usable(media_para)
    llm  = _unique_usable(media_llm)

    surf_vc = para["surface_meaning"].value_counts()
    deep_vc = llm["deeper_meaning"].value_counts()
    n_neither_surf = int(surf_vc.get("neither", 0))
    n_neither_deep = int(deep_vc.get("neither", 0))
    cats_3 = ["addiction", "attachment", "both"]
    colors_3 = [ADDICT, ATTACH, BOTH]
    S = COMPOSITE_LABEL_SCALE    # tick labels, panel titles, legend
    NUM_S = COMPOSITE_NUMBER_SCALE  # data value labels (bar-top counts + Panel-C in-bar numbers)
    AXT = COMPOSITE_AXISTITLE_SCALE  # axis titles ("Number of Paragraphs", "% of ...")

    # width 20 -> 22 (1.1x) gives Panel C's % axis 1.1x more horizontal room, so the
    # numbers in narrow segments sit less tightly (fonts are fixed pt, bars grow).
    fig = plt.figure(figsize=(22, 13))
    gs = GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.30,
                  height_ratios=[1, 2.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, :])

    # (A) Surface analysis totals
    s_vals = [int(surf_vc.get(c, 0)) for c in cats_3]
    x = np.arange(len(cats_3))
    bars = ax_a.bar(x, s_vals, width=0.55, color=colors_3, edgecolor="white")
    for bar, v in zip(bars, s_vals):
        ax_a.text(bar.get_x() + bar.get_width()/2, v + max(s_vals)*0.02,
                  f"{v:,}", ha="center", va="bottom", fontsize=16 * NUM_S, fontweight="bold")
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(["Addiction", "Attachment", "Both"], fontsize=16 * S)
    ax_a.set_ylabel("Number of Paragraphs", fontsize=14 * AXT)     # axis title
    ax_a.set_title("(A) Surface Analysis", fontsize=20 * S, fontweight="bold")
    ax_a.set_ylim(0, max(s_vals) * 1.32)
    ax_a.tick_params(axis="x", length=0)
    ax_a.tick_params(axis="y", labelsize=13 * S)

    # (B) Deeper analysis totals
    d_vals = [int(deep_vc.get(c, 0)) for c in cats_3]
    bars2 = ax_b.bar(x, d_vals, width=0.55, color=colors_3, edgecolor="white")
    for bar, v in zip(bars2, d_vals):
        ax_b.text(bar.get_x() + bar.get_width()/2, v + max(d_vals)*0.02,
                  f"{v:,}", ha="center", va="bottom", fontsize=16 * NUM_S, fontweight="bold")
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(["Addiction", "Attachment", "Both"], fontsize=16 * S)
    ax_b.set_ylabel("Number of Paragraphs", fontsize=14 * AXT)     # axis title
    ax_b.set_title("(B) Deeper Analysis", fontsize=20 * S, fontweight="bold")
    ax_b.set_ylim(0, max(d_vals) * 1.32)
    ax_b.tick_params(axis="x", length=0)
    ax_b.tick_params(axis="y", labelsize=13 * S)

    # (C) Subset breakdown
    coded = llm[llm["deeper_meaning"].notna() & (llm["deeper_meaning"] != "")].copy()
    if PANEL_C_COMPACT:
        handles = _deeper_meaning_stack_compact(ax_c, coded, SUBSET_ORDER, SUBSET_LABEL,
                                                "paragraphs", scale=S, num_scale=NUM_S,
                                                floor_pct=PANEL_C_MIN_SEG_PCT, axtitle_scale=AXT)
    else:
        handles = _deeper_meaning_stack(ax_c, coded, SUBSET_ORDER, SUBSET_LABEL,
                                        "paragraphs", legend_in_axes=False, scale=S, num_scale=NUM_S,
                                        inside_pct=COMPOSITE_INBAR_MIN_PCT)
    ax_c.set_title(
        "(C) Deeper Analysis Within Each Surface Category",
        fontsize=20 * S, fontweight="bold", pad=14)

    fig.suptitle("Media Articles — Surface and Deeper-Level Analysis",
                 fontsize=23, fontweight="bold", y=1.06)          # chart title: unscaled
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.03),
               ncol=4, fontsize=14 * S, frameon=False)
    _fig_note(fig,
              f"Note: Paragraph-level classification units. 'Neither' category omitted from all panels "
              f"(surface n = {n_neither_surf:,}; deeper n = {n_neither_deep:,}).",
              y=0.0)
    plt.tight_layout()
    out = FIG_DIR / "figure2_media_composite.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────────
# Supplementary Figures
# ─────────────────────────────────────────────────────────────────────────
# Surface vocabulary counts (addiction/attachment/both), corpus-wide.
def surface_vocabulary_totals(media_para):
    media = _unique_usable(media_para)
    vc = media["surface_meaning"].value_counts()
    cats = ["addiction", "attachment", "both"]
    vals = [int(vc.get(c, 0)) for c in cats]
    colors = [ADDICT, ATTACH, BOTH]
    labels = ["Addiction\nVocabulary Only", "Attachment\nVocabulary Only", "Both"]

    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(len(cats))
    bars = ax.bar(x, vals, width=0.55, color=colors, edgecolor="white")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + max(vals)*0.02,
                f"{v:,}", ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Number of Paragraphs")
    ax.set_title("Surface Vocabulary in Media Articles", fontsize=12)
    ax.set_ylim(0, max(vals) * 1.32)
    ax.tick_params(axis="x", length=0)
    _fig_note(fig, f"Note: Paragraph-level classification units. 'Neither' n = {int(vc.get('neither',0)):,} omitted.")
    plt.tight_layout()
    out = FIG_DIR / "media_surface_vocabulary_totals.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Deeper-code distribution within each surface-vocabulary subset (stacked).
def deeper_meaning_by_vocabulary_subset(media_llm):
    media = _unique_usable(media_llm)
    coded = media[media["deeper_meaning"].notna() & (media["deeper_meaning"] != "")].copy()
    n_neither = int((media["deeper_meaning"].fillna("").str.lower() == "neither").sum())

    fig, ax = plt.subplots(figsize=(10, 6))
    _deeper_meaning_stack(ax, coded, SUBSET_ORDER, SUBSET_LABEL, "paragraphs")
    ax.set_title(
        "Deeper-Level Classifications for Each Surface-Level Classification Category",
        fontsize=11, fontweight="bold", pad=40)
    _fig_note(fig, f"Note: Paragraph-level classification units. 'Neither' n = {n_neither:,} included in bars above.")
    plt.tight_layout()
    out = FIG_DIR / "media_deeper_meaning_by_vocabulary_subset.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Surface-vs-deeper 2x4 heatmap (row-normalized %) + CSV of the crosstab.
def surface_vs_deeper_crosstab(media_llm):
    media = _unique_usable(media_llm)
    order = ["addiction", "attachment", "both", "neither"]
    surface = media["surface_meaning"].value_counts().reindex(order, fill_value=0)
    deeper  = media["deeper_meaning"].value_counts().reindex(order, fill_value=0)

    ct = pd.DataFrame([surface.values, deeper.values],
                      index=["Surface Meaning", "Deeper Meaning"], columns=order)
    ct["All"] = ct.sum(axis=1)
    ct.to_csv(OUTPUT_DIR / "media_surface_vs_deeper_crosstab.csv")

    counts = ct[order].values
    pct = counts / counts.sum(axis=1, keepdims=True) * 100

    fig, ax = plt.subplots(figsize=(9, 3.6))
    im = ax.imshow(pct, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(4)); ax.set_xticklabels([o.capitalize() for o in order])
    ax.set_yticks(range(2)); ax.set_yticklabels(["Surface Meaning", "Deeper Meaning"])
    _title_with_subtitle(
        ax, "Media Articles: Surface vs. Deeper Meaning",
        f"(N = {int(counts[0].sum()):,} paragraphs each row; colour = % of row)")
    for i in range(2):
        for j in range(4):
            ax.text(j, i, f"{counts[i, j]:,}\n{pct[i, j]:.0f}%", ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="white" if pct[i, j] > 55 else "#222")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="% of Row")
    plt.tight_layout()
    out = FIG_DIR / "media_surface_vs_deeper_crosstab.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote media_surface_vs_deeper_crosstab.csv + {out.name}  "
          f"(N = {int(counts[0].sum()):,})")


# ─────────────────────────────────────────────────────────────────────────
def main():
    media_para = pd.read_excel(MEDIA_PARA)
    media_llm  = pd.read_excel(MEDIA_LLM)

    media_para_u = _unique_usable(media_para)
    media_llm_u  = _unique_usable(media_llm)

    # ── Manuscript figure ───────────────────────────────────────────────
    figure2_media_composite(media_para, media_llm)

    # ── Supplementary ───────────────────────────────────────────────────
    surface_vocabulary_totals(media_para)
    deeper_meaning_totals(media_llm_u, corpus_label="media articles", file_prefix="media")
    deeper_meaning_by_vocabulary_subset(media_llm)
    surface_vs_deeper_crosstab(media_llm)
    surface_and_deeper_totals(media_para_u, media_llm_u,
                              corpus_label="media articles", file_prefix="media")

    print(f"\nAll media figures saved to {FIG_DIR.resolve()}")


if __name__ == "__main__":
    main()
