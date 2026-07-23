#!/usr/bin/env python3
"""Shared figure infrastructure (paths, palette, rcParams, plotting helpers, and
two corpus-parameterised figure functions) imported by legal_figures.py and
media_figures.py so neither imports from the other.

Import side effects only: creates figures/ and output/ and sets rcParams; reads
no data and renders no figures.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

ROOT       = Path(__file__).resolve().parent.parent
FIG_DIR    = ROOT / "figures"
OUTPUT_DIR = ROOT / "output"
DATA_DIR   = ROOT / "modified_data"
FIG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── palette ──────────────────────────────────────────────────────────────
ADDICT  = "#c0392b"
ATTACH  = "#2980b9"
BOTH    = "#7d3c98"
NEITHER = "#bdc3c7"

CODE_COLORS = {
    "addiction":  ADDICT,
    "attachment": ATTACH,
    "both":       BOTH,
    "neither":    NEITHER,
}

# ── composite-figure scales (REVERT KNOBS) ───────────────────────────────
# Multipliers applied ONLY to the two manuscript composites
# (figure1_legal_composite / figure2_media_composite). Set both to 1.0 to revert.
#
# LABEL scale: tick labels, the (A)/(B)/(C) panel titles, Panel-C row labels,
#   and the legend. Does NOT touch the figure suptitle ("chart title") or the
#   axis titles ("Number of Paragraphs", "% of Paragraphs", "Surface Category").
# NUMBER scale: the data value labels only — the bar-top counts in panels A/B
#   and the "count (pct%)" in-bar labels + callouts in Panel C.
COMPOSITE_LABEL_SCALE = 1.25
COMPOSITE_NUMBER_SCALE = 1.20
# Axis titles ("Number of Paragraphs", "% of Paragraphs"). Kept at 1.0 initially so
# they stayed out of the label scale-up; raised to match the tick labels once the
# widened layout left room. The figure suptitle is still deliberately excluded.
COMPOSITE_AXISTITLE_SCALE = 1.25
# Panel-C segments narrower than this (% of row) put their label in an above-bar
# callout (leader line + segment colour) instead of inside the bar. Raised from the
# 4.0 default so the media "Neither" row's 4.6% attachment sliver (967) — too narrow
# to hold its label cleanly inside — becomes a callout like the other small segments.
COMPOSITE_INBAR_MIN_PCT = 5.0

# Panel-C compact layout (REVERT KNOB). When True, Panel C reclaims the left margin
# (row labels move ABOVE each bar), bars fill the full width and are taller, and a
# small minimum-segment-width floor lets every count sit INSIDE its bar — no more
# leader-line callouts. Set False to restore the classic left-labelled layout with
# arrows. PANEL_C_MIN_SEG_PCT is the floor (% of a row) applied only in compact mode:
# slices narrower than it are widened just enough to hold their label, borrowing the
# width from the row's dominant slice. Printed counts and percentages stay exact.
PANEL_C_COMPACT = True
PANEL_C_MIN_SEG_PCT = 3.3

USER_C    = "#16a085"
CHATBOT_C = "#e67e22"
BOTH_BC   = "#7d3c98"
UNCLEAR_C = "#95a5a6"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "legend.frameon": False,
})


def _title_with_subtitle(ax, main, sub, main_size=12, sub_size=9):
    """Bold main title up top with a smaller italic subtitle just under it."""
    ax.set_title(main, fontsize=main_size, pad=22)
    ax.text(0.5, 1.005, sub, transform=ax.transAxes,
            ha="center", va="bottom", fontsize=sub_size, style="italic", color="#555")


def _fig_note(fig, text, y=-0.02):
    """No-op: figure notes are turned off to keep the panels clean. Kept so call
    sites don't need to change; re-enable the body below to restore notes."""
    return


# Row labels for the Panel-C stacked bars: just the surface category + its n.
# The shared heading "Surface Category" is set as the y-axis label in _deeper_meaning_stack.
SUBSET_LABEL = {
    "addiction":  "Addiction",
    "attachment": "Attachment",
    "both":       "Both",
    "neither":    "Neither",
}
SUBSET_ORDER = ["addiction", "attachment", "both", "neither"]


# ─────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────
def _barh_stack(ax, y, pct_rows, count_rows, colors, labels,
                inside_pct=4.0, fontsize=14, bar_h=0.62, text_color_map=None,
                scale=1.0):
    # `scale` multiplies every text size in this stack (in-bar labels + callouts);
    # 1.0 leaves supplementary figures unchanged, composites pass > 1.0.
    fontsize = fontsize * scale
    # Every non-zero segment is labelled "count (pct%)". Segments >= inside_pct
    # get the label INSIDE the bar (font flexes down for narrow segments so even a
    # ~4-5% segment holds its label); only sub-inside_pct slivers become callouts
    # above the bar, tied by a leader. Callouts within a row are laid out
    # monotonically (sorted by segment centre, pushed right by a min gap, and
    # staggered over three heights) so leaders never cross.
    left = np.zeros(len(y))
    above = {i: [] for i in range(len(y))}          # per-row above-bar callouts
    for label, color in zip(labels, colors):
        widths = [row.get(label, 0) for row in pct_rows]
        counts = [row.get(label, 0) for row in count_rows]
        ax.barh(y, widths, left=left, color=color,
                edgecolor="white", linewidth=0.7, height=bar_h)
        for i, (w, cnt) in enumerate(zip(widths, counts)):
            if cnt == 0:
                continue
            pct_str = f"{w:.0f}%" if w >= 1 else "<1%"
            txt = f"{int(cnt):,} ({pct_str})"
            tc = "white"
            if text_color_map and label in text_color_map:
                tc = text_color_map[label]
            elif label == "neither":
                tc = "#222"
            if w >= inside_pct:
                fs = fontsize if w >= 8 else fontsize - 3   # flex down in narrow bars
                ax.text(left[i] + w / 2, y[i], txt,
                        ha="center", va="center",
                        fontsize=fs, color=tc, fontweight="bold")
            else:
                lab_color = "#555" if label == "neither" else color
                above[i].append((left[i] + w / 2, txt, lab_color))
        left = left + np.array(widths)

    # lay out the above-bar callouts for each row without overlap
    min_gap = 11.0                                  # min horizontal spacing (% units)
    for i, items in above.items():
        items.sort(key=lambda t: t[0])              # by true segment centre
        last_tx = -1e9
        for k, (cx, txt, lab_color) in enumerate(items):
            tx = min(max(max(cx, last_tx + min_gap), 6), 94)
            last_tx = tx
            dy = 0.52 + 0.30 * (k % 3)              # three-level vertical stagger
            ax.annotate(txt, xy=(cx, y[i] - bar_h / 2 + 0.02), xytext=(tx, y[i] - dy),
                        ha="center", va="center", fontsize=fontsize - 1,
                        fontweight="bold", color=lab_color,
                        arrowprops=dict(arrowstyle="-", color="#999", lw=0.9))


def _ensure_mentions(df: pd.DataFrame) -> pd.DataFrame:
    # Derive boolean per-code flags; "both" counts toward both addiction & attachment.
    df = df.copy()
    code = df["deeper_meaning"].fillna("").astype(str).str.lower()
    df["is_addiction"]  = code.isin(["addiction", "both"])
    df["is_attachment"] = code.isin(["attachment", "both"])
    return df


def _deeper_meaning_stack(ax, df, subset_order, subset_label, unit, legend_in_axes=True,
                          scale=1.0, num_scale=None, inside_pct=4.0):
    # `scale` enlarges tick labels (row labels + x ticks) and the in-axes legend —
    # but NOT the axis titles ("Surface Category", "% of ..."). `num_scale` sizes the
    # in-bar "count (pct%)" labels/callouts separately (defaults to `scale`).
    # `inside_pct` = segment-width threshold below which a label becomes a callout.
    if num_scale is None:
        num_scale = scale
    code_labels = ["addiction", "attachment", "both", "neither"]
    code_colors = [CODE_COLORS[f] for f in code_labels]

    # One horizontal stacked bar per surface-vocab subset, split by deeper-meaning share.
    pct_rows, cnt_rows, y_labels, y_pos = [], [], [], []
    for i, name in enumerate(subset_order):
        sub = df[df["surface_meaning"] == name]
        n = len(sub)
        if n == 0:
            continue
        vc = sub["deeper_meaning"].value_counts()
        cnts = {f: int(vc.get(f, 0)) for f in code_labels}
        pct_rows.append({k: 100 * v / n for k, v in cnts.items()})
        cnt_rows.append(cnts)
        y_labels.append(f"{subset_label[name]} (n = {n:,})")
        y_pos.append(i)

    # widen the vertical spacing between rows so above-bar callouts have room
    ROW_SP = 1.7
    y = np.array(y_pos) * ROW_SP
    _barh_stack(ax, y, pct_rows, cnt_rows, code_colors, code_labels,
                inside_pct=inside_pct, scale=num_scale)
    ax.set_yticks(y); ax.set_yticklabels(y_labels, fontsize=15 * scale)
    # labelpad pushes the axis title left so it clears the long tick labels
    ax.set_ylabel("Surface Category", fontsize=15, fontweight="bold", labelpad=18)
    ax.set_ylim(y.max() + 0.95, y.min() - 1.35)  # inverted, with room for above-bar counts
    ax.set_xlim(0, 100)
    ax.set_xlabel(f"% of {unit.capitalize()}", fontsize=14)
    ax.tick_params(axis="x", labelsize=14 * scale)
    handles = [mpatches.Patch(color=c, label=l.capitalize())
               for c, l in zip(code_colors, code_labels)]
    if legend_in_axes:
        ax.legend(handles=handles, loc="upper left",
                  bbox_to_anchor=(0, 1.10), fontsize=10 * scale, ncol=4)
    return handles


def _deeper_meaning_stack_compact(ax, df, subset_order, subset_label, unit,
                                  scale=1.0, num_scale=None, floor_pct=3.3,
                                  axtitle_scale=1.0):
    """Compact Panel-C: row labels sit ABOVE each bar (freeing the whole left margin
    for full-width bars), bars are taller, and every count sits INSIDE its bar — no
    leader callouts. Slices narrower than `floor_pct` are widened just enough to hold
    their label, borrowing that width from the row's dominant slice; the printed count
    and percentage are always the true values (a footnote flags the widening)."""
    if num_scale is None:
        num_scale = scale
    code_labels = ["addiction", "attachment", "both", "neither"]
    code_colors = [CODE_COLORS[f] for f in code_labels]

    rows, y_pos = [], []
    for i, name in enumerate(subset_order):
        sub = df[df["surface_meaning"] == name]
        n = len(sub)
        if n == 0:
            continue
        vc = sub["deeper_meaning"].value_counts()
        cnts = {f: int(vc.get(f, 0)) for f in code_labels}
        pct_true = {k: 100 * v / n for k, v in cnts.items()}
        # widen any sub-floor slice to floor_pct; take the borrowed width off the widest
        pct_draw = dict(pct_true)
        deficit = sum(floor_pct - pct_draw[k]
                      for k in code_labels if 0 < pct_draw[k] < floor_pct)
        for k in code_labels:
            if 0 < pct_draw[k] < floor_pct:
                pct_draw[k] = floor_pct
        if deficit > 0:
            biggest = max(code_labels, key=lambda k: pct_draw[k])
            pct_draw[biggest] -= deficit
        rows.append(dict(pct_true=pct_true, pct_draw=pct_draw, cnt=cnts,
                         name=subset_label[name], n=n))
        y_pos.append(i)

    ROW_SP, bar_h = 1.4, 0.94
    y = np.array(y_pos) * ROW_SP
    fs_base = 14 * num_scale

    left = np.zeros(len(rows))
    for label, color in zip(code_labels, code_colors):
        widths = np.array([r["pct_draw"].get(label, 0) for r in rows])
        ax.barh(y, widths, left=left, color=color,
                edgecolor="white", linewidth=0.8, height=bar_h)
        for i, r in enumerate(rows):
            cnt = r["cnt"].get(label, 0)
            if cnt == 0:
                continue
            wt = r["pct_true"].get(label, 0)
            main_str = f"{wt:.0f}%" if wt >= 1 else "<1%"   # percentage is the headline
            sub_str = f"({int(cnt):,})"                      # raw count in parentheses
            tc = "#222" if label == "neither" else "white"
            cx = left[i] + widths[i] / 2
            # big % on top, small (count) beneath; the % shrinks a touch in the narrow
            # (floored) slices so it still fits horizontally
            main_fs = fs_base * (1.18 if wt >= 4 else 1.06)
            sub_fs = fs_base * 0.76
            # y-axis is inverted here, so a smaller y sits higher on screen: the % goes
            # just above the row centre, the (count) just below, with a clear gap.
            ax.text(cx, y[i] - 0.13, main_str, ha="center", va="center",
                    fontsize=main_fs, color=tc, fontweight="bold")
            ax.text(cx, y[i] + 0.11, sub_str, ha="center", va="center",
                    fontsize=sub_fs, color=tc, fontweight="bold")
        left = left + widths

    # row labels stay LEFT of the axis; n moves to a second line under the category
    # name (narrower than the one-line form, so the bars still gain a little width).
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['name']}\n(n = {r['n']:,})" for r in rows],
                       fontsize=15 * scale)
    ax.set_ylabel("")
    ax.set_xlim(0, 100)
    # tight top/bottom padding → less dead white space inside Panel C
    ax.set_ylim(y.max() + bar_h / 2 + 0.35, y.min() - bar_h / 2 - 0.35)
    ax.set_xlabel(f"% of {unit.capitalize()} Within Surface Category",
                  fontsize=14 * axtitle_scale)
    ax.tick_params(axis="x", labelsize=14 * scale)
    return [mpatches.Patch(color=c, label=l.capitalize())
            for c, l in zip(code_colors, code_labels)]


# ─────────────────────────────────────────────────────────────────────────
# Shared supplementary figures (both corpora — parameterised by corpus)
# ─────────────────────────────────────────────────────────────────────────
def deeper_meaning_totals(llm_df, corpus_label="legal complaints", file_prefix="legal"):
    # Bar chart of the three substantive codes; "neither" is dropped (dominant).
    coded = llm_df[llm_df["deeper_meaning"].fillna("") != ""]
    vc = coded["deeper_meaning"].value_counts()
    cats = ["addiction", "attachment", "both"]
    vals = [int(vc.get(c, 0)) for c in cats]
    colors = [ADDICT, ATTACH, BOTH]
    labels = ["Addiction", "Attachment", "Both"]

    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(len(cats))
    bars = ax.bar(x, vals, width=0.55, color=colors, edgecolor="white")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + max(vals)*0.02,
                f"{v:,}", ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Number of Paragraphs")
    corpus_title = " ".join(w.capitalize() for w in corpus_label.split())
    ax.set_title(f"Deeper Meaning in {corpus_title}", fontsize=12)
    ax.set_ylim(0, max(vals) * 1.32)
    ax.tick_params(axis="x", length=0)
    _fig_note(fig, f"Note: Paragraph-level classification units. 'Neither' n = {int(vc.get('neither', 0)):,} omitted.")
    plt.tight_layout()
    out = FIG_DIR / f"{file_prefix}_deeper_meaning_totals.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")


def surface_and_deeper_totals(para_df, llm_df, corpus_label="legal complaints", file_prefix="legal"):
    # Two stacked panels: surface vocabulary counts (top) vs LLM deeper coding (bottom).
    cats = ["addiction", "attachment", "both", "neither"]
    colors = [ADDICT, ATTACH, BOTH, NEITHER]
    labels = ["Addiction", "Attachment", "Both", "Neither"]

    surface_vc = para_df["surface_meaning"].value_counts()
    deeper_vc = llm_df[llm_df["deeper_meaning"].fillna("") != ""]["deeper_meaning"].value_counts()
    s_vals = [int(surface_vc.get(c, 0)) for c in cats]
    d_vals = [int(deeper_vc.get(c, 0)) for c in cats]
    ymax = max(max(s_vals), max(d_vals)) * 1.18

    corpus_title = " ".join(w.capitalize() for w in corpus_label.split())
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for ax, vals, title, n_total in [
        (axes[0], s_vals, "Surface Meaning (Vocabulary)", sum(s_vals)),
        (axes[1], d_vals, "Deeper Meaning (LLM Coding)", sum(d_vals)),
    ]:
        x = np.arange(len(cats))
        bars = ax.bar(x, vals, width=0.6, color=colors, edgecolor="white")
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, v + ymax*0.012,
                    f"{v:,}", ha="center", va="bottom", fontsize=11, fontweight="bold")
        ax.set_ylim(0, ymax)
        ax.set_ylabel("Number of Paragraphs")
        ax.set_title(f"{title}  (N = {n_total:,})", fontsize=10)
        ax.tick_params(axis="x", length=0)

    axes[1].set_xticks(np.arange(len(cats)))
    axes[1].set_xticklabels(labels, fontsize=11)
    fig.suptitle(f"Surface vs. Deeper Meaning — {corpus_title}",
                 fontsize=13, fontweight="bold", y=1.00)
    plt.tight_layout()
    out = FIG_DIR / f"{file_prefix}_surface_and_deeper_totals.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"wrote {out.name}")
