#!/usr/bin/env python3
"""
Render all legal-corpus figures from legal_paragraphs_24_llm_v9p2.xlsx
(surface + deeper LLM coding, 24 complaints); outputs to figures/.

Palette and plotting helpers are shared via figures_common (parallels media_figures.py).
"""

from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from figures_common import (
    FIG_DIR, OUTPUT_DIR, DATA_DIR,
    ADDICT, ATTACH, BOTH, NEITHER, CODE_COLORS,
    SUBSET_LABEL, SUBSET_ORDER,
    COMPOSITE_LABEL_SCALE, COMPOSITE_NUMBER_SCALE, COMPOSITE_INBAR_MIN_PCT,
    COMPOSITE_AXISTITLE_SCALE, PANEL_C_COMPACT, PANEL_C_MIN_SEG_PCT,
    _title_with_subtitle, _fig_note, _deeper_meaning_stack, _deeper_meaning_stack_compact,
    deeper_meaning_totals, surface_and_deeper_totals,
)

LEGAL_PARA = DATA_DIR / "legal_paragraphs_24_llm_v9p2.xlsx"
LEGAL_LLM  = OUTPUT_DIR / "legal_paragraphs_24_llm_v9p2.xlsx"


# ─────────────────────────────────────────────────────────────────────────
# Manuscript Figures
# ─────────────────────────────────────────────────────────────────────────
# Manuscript Fig 1: surface vs. deeper totals + per-surface-subset deeper breakdown.
def figure1_legal_composite(legal_para, legal_llm):
    """Figure 1: (a) surface totals | (b) deeper totals | (c) subset breakdown."""
    surf_vc = legal_para["surface_meaning"].value_counts()
    deep_vc = legal_llm["deeper_meaning"].value_counts()
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
    coded = legal_llm[legal_llm["deeper_meaning"].notna() &
                      (legal_llm["deeper_meaning"] != "")].copy()
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

    fig.suptitle("Legal Complaints — Surface and Deeper-Level Analysis",
                 fontsize=23, fontweight="bold", y=1.06)          # chart title: unscaled
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.03),
               ncol=4, fontsize=14 * S, frameon=False)
    _fig_note(fig,
              f"Note: Paragraph-level classification units. 'Neither' category omitted from all panels "
              f"(surface n = {n_neither_surf:,}; deeper n = {n_neither_deep:,}).",
              y=0.0)
    plt.tight_layout()
    out = FIG_DIR / "figure1_legal_composite.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Manuscript Fig 3: grouped bars of surface vs. deeper counts, one group per complaint.
def figure3_per_case_legal(legal_para, legal_llm):
    """Figure 3: (a) surface per complaint | (b) deeper per complaint."""
    cats = ["addiction", "attachment", "both"]
    colors = [ADDICT, ATTACH, BOTH]
    labels = ["Addiction Only", "Attachment Only", "Both"]

    surf = (legal_para.groupby("case")["surface_meaning"].value_counts()
                      .unstack(fill_value=0).reindex(columns=cats, fill_value=0))
    deep = (legal_llm.groupby("case")["deeper_meaning"].value_counts()
                     .unstack(fill_value=0).reindex(columns=cats, fill_value=0))

    order = deep.sum(axis=1).sort_values(ascending=False).index
    surf = surf.reindex(order); deep = deep.reindex(order)
    ymax = max(surf.values.max(), deep.values.max()) * 1.12

    fig, axes = plt.subplots(2, 1, figsize=(17, 9), sharex=True)
    x = np.arange(len(order))
    w = 0.27
    for ax, df_, panel_label, title in [
        (axes[0], surf, "(a)", "Surface Vocabulary per Legal Complaint"),
        (axes[1], deep, "(b)", "Deeper Meaning per Legal Complaint"),
    ]:
        ax.bar(x - w, df_["addiction"],  w, label=labels[0], color=colors[0])
        ax.bar(x,     df_["attachment"], w, label=labels[1], color=colors[1])
        ax.bar(x + w, df_["both"],       w, label=labels[2], color=colors[2])
        ax.set_ylim(0, ymax)
        ax.set_ylabel("Number of Paragraphs")
        ax.set_title(f"{panel_label} {title}", fontsize=11, fontweight="bold")
        ax.legend(loc="upper right", ncol=3)

    axes[1].set_xticks(x)
    axes[1].set_xticklabels([c.replace("_", " ") for c in order],
                             rotation=35, ha="right")
    fig.suptitle("Legal Complaints — Classifications by Case",
                 fontsize=13, fontweight="bold", y=1.01)
    _fig_note(fig, "Note: Paragraph-level classification units. 'Neither' category omitted.")
    plt.tight_layout()
    out = FIG_DIR / "figure3_per_case_legal.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────────
# Supplementary Figures
# ─────────────────────────────────────────────────────────────────────────
# Surface vocabulary counts (addiction/attachment/both), corpus-wide.
def surface_vocabulary_totals(legal_para):
    n_total = len(legal_para)
    vc = legal_para["surface_meaning"].value_counts()
    cats = ["addiction", "attachment", "both"]
    vals = [int(vc.get(c, 0)) for c in cats]
    colors = [ADDICT, ATTACH, BOTH]
    labels = ["Addiction\nVocabulary Only", "Attachment\nVocabulary Only", "Both"]

    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(len(cats))
    bars = ax.bar(x, vals, width=0.55, color=colors, edgecolor="white")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + max(vals)*0.02,
                f"{v}", ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Number of Paragraphs")
    ax.set_title("Surface Vocabulary in Legal Complaints", fontsize=12)
    ax.set_ylim(0, max(vals) * 1.32)
    ax.tick_params(axis="x", length=0)
    _fig_note(fig, f"Note: Paragraph-level classification units. 'Neither' n = {int(vc.get('neither',0)):,} omitted.")
    plt.tight_layout()
    out = FIG_DIR / "legal_surface_vocabulary_totals.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Surface vocabulary grouped bars, one group per complaint.
def surface_vocabulary_per_case(legal_para):
    ct = (legal_para.groupby("case")["surface_meaning"].value_counts()
                    .unstack(fill_value=0)
                    .reindex(columns=["addiction", "attachment", "both"], fill_value=0))
    ct["total"] = ct.sum(axis=1)
    ct = ct.sort_values("total", ascending=False)

    fig, ax = plt.subplots(figsize=(14, 5.5))
    x = np.arange(len(ct))
    w = 0.27
    ax.bar(x - w, ct["addiction"], w, label="Addiction Only", color=ADDICT)
    ax.bar(x,     ct["attachment"], w, label="Attachment Only", color=ATTACH)
    ax.bar(x + w, ct["both"],        w, label="Both", color=BOTH)
    ax.set_xticks(x)
    ax.set_xticklabels(ct.index.str.replace("_", " "), rotation=35, ha="right")
    ax.set_ylabel("Number of Paragraphs")
    ax.set_title("Surface Vocabulary by Legal Complaint", fontsize=12)
    ax.legend(loc="upper right")
    plt.tight_layout()
    out = FIG_DIR / "legal_surface_vocabulary_per_case.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Deeper-code distribution within each surface-vocabulary subset (stacked).
def deeper_meaning_by_vocabulary_subset(legal):
    coded = legal[legal["deeper_meaning"].notna() & (legal["deeper_meaning"] != "")].copy()
    n_neither = int((legal["deeper_meaning"].fillna("").str.lower() == "neither").sum())

    fig, ax = plt.subplots(figsize=(10, 6))
    _deeper_meaning_stack(ax, coded, SUBSET_ORDER, SUBSET_LABEL, "paragraphs")
    ax.set_title(
        "Deeper-Level Classifications for Each Surface-Level Classification Category",
        fontsize=11, fontweight="bold", pad=40)
    _fig_note(fig, f"Note: Paragraph-level classification units. 'Neither' n = {n_neither:,} included in bars above.")
    plt.tight_layout()
    out = FIG_DIR / "legal_deeper_meaning_by_vocabulary_subset.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Helper: per-case deeper-code counts, ordered by substantive (non-neither) volume.
def _per_case_counts(legal):
    codes = ["addiction", "attachment", "both", "neither"]
    counts = (legal.groupby("case")["deeper_meaning"]
                   .value_counts().unstack(fill_value=0)
                   .reindex(columns=codes, fill_value=0))
    counts["substantive"] = counts["addiction"] + counts["attachment"] + counts["both"]
    counts = counts.sort_values("substantive", ascending=False).drop(columns="substantive")
    return counts


# Deeper codes per complaint, stacked absolute counts (incl. neither).
def deeper_meaning_per_case_counts(legal):
    counts = _per_case_counts(legal)
    codes = ["addiction", "attachment", "both", "neither"]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(counts))
    bottom = np.zeros(len(counts))
    for code in codes:
        vals = counts[code].values
        ax.bar(x, vals, 0.6, bottom=bottom, label=code.capitalize(),
               color=CODE_COLORS[code])
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(counts.index.str.replace("_", " "), rotation=35, ha="right")
    ax.set_ylabel("Number of Paragraphs")
    ax.set_title("Deeper Meaning by Legal Complaint — Paragraph Counts")
    ax.legend(loc="upper right", ncol=4)
    plt.tight_layout()
    out = FIG_DIR / "legal_deeper_meaning_per_case_counts.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Deeper codes per complaint, stacked to 100% (share within each case).
def deeper_meaning_per_case_percent(legal):
    counts = _per_case_counts(legal)
    codes = ["addiction", "attachment", "both", "neither"]
    props = counts.div(counts.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(props))
    bottom = np.zeros(len(props))
    for code in codes:
        vals = props[code].values
        ax.bar(x, vals, 0.6, bottom=bottom, label=code.capitalize(),
               color=CODE_COLORS[code])
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(props.index.str.replace("_", " "), rotation=35, ha="right")
    ax.set_ylabel("Share of Paragraphs (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Deeper Meaning by Legal Complaint — % of Paragraphs")
    ax.legend(loc="upper right", ncol=4)
    plt.tight_layout()
    out = FIG_DIR / "legal_deeper_meaning_per_case_percent.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Same per-case stack but substantive codes only (neither dropped).
def deeper_meaning_per_case_excluding_neither(legal):
    counts = _per_case_counts(legal)
    sub = counts[["addiction", "attachment", "both"]]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(sub))
    bottom = np.zeros(len(sub))
    for code in ["addiction", "attachment", "both"]:
        vals = sub[code].values
        ax.bar(x, vals, 0.6, bottom=bottom, label=code.capitalize(),
               color=CODE_COLORS[code])
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(sub.index.str.replace("_", " "), rotation=35, ha="right")
    ax.set_ylabel("Number of Paragraphs")
    ax.set_title("Deeper Meaning by Legal Complaint — Excluding 'Neither'")
    ax.legend(loc="upper right", ncol=3)
    _fig_note(ax.get_figure(), "Note: 'Neither' category omitted.")
    plt.tight_layout()
    out = FIG_DIR / "legal_deeper_meaning_per_case_excluding_neither.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Surface vs. deeper grouped bars per case, stacked in two rows (unlabeled variant of Fig 3).
def surface_and_deeper_per_case(legal_para, legal_llm):
    cats = ["addiction", "attachment", "both"]
    colors = [ADDICT, ATTACH, BOTH]
    labels = ["Addiction Only", "Attachment Only", "Both"]

    surf = (legal_para.groupby("case")["surface_meaning"].value_counts()
                      .unstack(fill_value=0).reindex(columns=cats, fill_value=0))
    deep = (legal_llm.groupby("case")["deeper_meaning"].value_counts()
                     .unstack(fill_value=0).reindex(columns=cats, fill_value=0))

    order = deep.sum(axis=1).sort_values(ascending=False).index
    surf = surf.reindex(order); deep = deep.reindex(order)
    ymax = max(surf.values.max(), deep.values.max()) * 1.12

    fig, axes = plt.subplots(2, 1, figsize=(13, 8.5), sharex=True)
    x = np.arange(len(order))
    w = 0.27
    for ax, df_, title in [
        (axes[0], surf, "Surface Meaning (Vocabulary) per Case"),
        (axes[1], deep, "Deeper Meaning (LLM Coding) per Case"),
    ]:
        ax.bar(x - w, df_["addiction"],  w, label=labels[0], color=colors[0])
        ax.bar(x,     df_["attachment"], w, label=labels[1], color=colors[1])
        ax.bar(x + w, df_["both"],       w, label=labels[2], color=colors[2])
        ax.set_ylim(0, ymax)
        ax.set_ylabel("Number of Paragraphs")
        ax.set_title(title, fontsize=10)

    axes[1].set_xticks(x)
    axes[1].set_xticklabels([c.replace("_", " ") for c in order], rotation=35, ha="right")
    axes[0].legend(loc="upper right", ncol=3)
    fig.suptitle("Surface vs. Deeper Meaning per Case — Legal Complaints",
                 fontsize=13, fontweight="bold", y=1.00)
    _fig_note(fig, "Note: 'Neither' category omitted.")
    plt.tight_layout()
    out = FIG_DIR / "legal_surface_and_deeper_per_case.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


# Surface-vs-deeper 2x4 heatmap (row-normalized %) + CSV of the crosstab.
def surface_vs_deeper_crosstab(legal):
    order = ["addiction", "attachment", "both", "neither"]
    surface = legal["surface_meaning"].value_counts().reindex(order, fill_value=0)
    deeper  = legal["deeper_meaning"].value_counts().reindex(order, fill_value=0)

    ct = pd.DataFrame([surface.values, deeper.values],
                      index=["Surface Meaning", "Deeper Meaning"], columns=order)
    ct["All"] = ct.sum(axis=1)
    ct.to_csv(OUTPUT_DIR / "legal_surface_vs_deeper_crosstab.csv")

    counts = ct[order].values
    pct = counts / counts.sum(axis=1, keepdims=True) * 100

    fig, ax = plt.subplots(figsize=(9, 3.6))
    im = ax.imshow(pct, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(4)); ax.set_xticklabels([o.capitalize() for o in order])
    ax.set_yticks(range(2)); ax.set_yticklabels(["Surface Meaning", "Deeper Meaning"])
    _title_with_subtitle(
        ax, "Legal Complaints: Surface vs. Deeper Meaning",
        f"(N = {int(counts[0].sum())} paragraphs each row; colour = % of row)")
    for i in range(2):
        for j in range(4):
            ax.text(j, i, f"{counts[i, j]}\n{pct[i, j]:.0f}%", ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="white" if pct[i, j] > 55 else "#222")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="% of Row")
    plt.tight_layout()
    out = FIG_DIR / "legal_surface_vs_deeper_crosstab.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote legal_surface_vs_deeper_crosstab.csv + {out.name}  "
          f"(N = {int(counts[0].sum())})")


# ─────────────────────────────────────────────────────────────────────────
def main():
    legal_para = pd.read_excel(LEGAL_PARA)
    legal_llm  = pd.read_excel(LEGAL_LLM)

    # ── Manuscript figures ──────────────────────────────────────────────
    figure1_legal_composite(legal_para, legal_llm)
    figure3_per_case_legal(legal_para, legal_llm)

    # ── Supplementary ───────────────────────────────────────────────────
    surface_vocabulary_totals(legal_para)
    deeper_meaning_totals(legal_llm)
    deeper_meaning_by_vocabulary_subset(legal_llm)
    surface_vs_deeper_crosstab(legal_llm)
    surface_and_deeper_totals(legal_para, legal_llm)
    surface_vocabulary_per_case(legal_para)
    deeper_meaning_per_case_counts(legal_llm)
    deeper_meaning_per_case_percent(legal_llm)
    deeper_meaning_per_case_excluding_neither(legal_llm)
    surface_and_deeper_per_case(legal_para, legal_llm)

    print(f"\nAll figures saved to {FIG_DIR.resolve()}")


if __name__ == "__main__":
    main()
