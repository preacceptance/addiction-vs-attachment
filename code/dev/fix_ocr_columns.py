#!/usr/bin/env python3
"""
Column-aware re-extraction of OCR'd chat-screenshot pages.

Some legal-complaint exhibits embed chat screenshots laid out two (or more)
columns side by side on a page. The PDFs carry an upstream OCR text layer over
those images. pdfplumber rebuilds each pixel-row left-to-right across the FULL
page width with no column awareness, so it zippers the columns into character
salad (e.g. "A Y Y Y a t o n o o h s ...").

Fix: assign every char to a column band FIRST (clustered from the page's image
bounding boxes), then reflow each column independently — group chars into lines
by y, sort each line left-to-right by x. Columns are emitted left-to-right, so
each screenshot's text stays contiguous and legible.

This recovers the dialogue but does NOT re-insert inter-word spaces (pdfplumber
drops them on these pages); output is space-collapsed but readable. A separate
word-splitting pass could be added if needed.
"""

from __future__ import annotations

import pdfplumber

LINE_TOL = 3.5          # chars within this many points of y are one line
ROW_TOL = 20.0          # images whose y-ranges overlap by more than this are in the same row
GUTTER = 16.0           # an empty x-band at least this wide separates two columns


def split_columns_by_xgap(chars: list[dict]) -> list[list[dict]]:
    """Split a region's chars into columns at empty vertical gutters.

    A true column gap is an x-range crossed by no character of any line, so it
    shows up as a gap >= GUTTER between consecutive occupied x positions. A single
    text column has no such gap (every x from left to right margin is occupied by
    some line). Returns columns left-to-right.
    """
    if not chars:
        return []
    xs = sorted({round(c["x0"], 1) for c in chars})
    cuts = [(a + b) / 2 for a, b in zip(xs, xs[1:]) if b - a >= GUTTER]
    if not cuts:
        return [chars]
    bounds = [-1e9] + cuts + [1e9]
    cols = []
    for lo, hi in zip(bounds, bounds[1:]):
        col = [c for c in chars if lo <= c["x0"] < hi]
        if col:
            cols.append(col)
    return cols


def reflow_chars(chars: list[dict]) -> str:
    """Group chars into lines by y, order each line left-to-right; join lines with newlines."""
    if not chars:
        return ""
    chars = sorted(chars, key=lambda c: c["top"])
    lines: list[list[dict]] = []
    cur: list[dict] = [chars[0]]
    cur_y = chars[0]["top"]
    for c in chars[1:]:
        if abs(c["top"] - cur_y) <= LINE_TOL:
            cur.append(c)
        else:
            lines.append(cur)
            cur = [c]
            cur_y = c["top"]
    lines.append(cur)
    out = []
    for ln in lines:
        out.append("".join(c["text"] for c in sorted(ln, key=lambda c: c["x0"])))
    return "\n".join(out)


def page_is_multicol(page) -> bool:
    """True if two images overlap vertically but are horizontally separated (side-by-side)."""
    imgs = page.images
    for a in range(len(imgs)):
        for b in range(a + 1, len(imgs)):
            A, B = imgs[a], imgs[b]
            y_overlap = min(A["bottom"], B["bottom"]) - max(A["top"], B["top"])
            x_separate = (A["x0"] >= B["x1"]) or (B["x0"] >= A["x1"])
            if y_overlap > 20 and x_separate:
                return True
    return False


def chars_in_bbox(chars, x0, x1, top, bottom):
    return [c for c in chars
            if x0 - 1 <= c["x0"] <= x1 + 1 and top - 1 <= c["top"] <= bottom + 1]


def extract_screenshot_text(page) -> str:
    """Recover dialogue from screenshot images on a page, one image at a time.

    Each screenshot is a single image object with a known bbox; its OCR chars all
    fall inside that bbox. Extracting per image avoids zippering side-by-side
    columns and never touches full-width body prose (which is not inside an image).
    Images are emitted top-to-bottom, then left-to-right within a row.
    """
    imgs = sorted(page.images, key=lambda im: (round(im["top"] / ROW_TOL), im["x0"]))
    chars = page.chars
    blocks = []
    for im in imgs:
        cell = chars_in_bbox(chars, im["x0"], im["x1"], im["top"], im["bottom"])
        for col in split_columns_by_xgap(cell):     # handle sub-columns inside one image
            block = reflow_chars(col)
            if block.strip():
                blocks.append(block)
    return "\n".join(blocks)


import re

# Survives space-collapse: "AssistantonMay22,2025at09:28:35PMEDT", "useratJul25,2025at04:11:08AMCDT"
TS_RE = re.compile(
    r"(?:assistant|user)\s*on?\s*"
    r"([A-Z][a-z]{2}\s*\d{1,2}\s*,?\s*20\d\d)\s*at?\s*(\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2})",
    re.IGNORECASE,
)


def ts_key(text: str) -> str | None:
    """Normalized timestamp key (date+time digits, no spaces) for the first timestamp in text."""
    m = TS_RE.search(text)
    if not m:
        return None
    return re.sub(r"\s+", "", (m.group(1) + m.group(2))).lower()


def screenshot_blocks(pdf_path: str) -> list[tuple[str | None, str]]:
    """All recovered screenshot blocks across the PDF, split per timestamp header.

    Returns (ts_key, block_text) in document order. Blocks without a timestamp
    header get ts_key=None (can't be anchor-matched — e.g. untimed UI screenshots).
    """
    doc = pdfplumber.open(pdf_path)
    blocks: list[tuple[str | None, str]] = []
    for pg in doc.pages:
        if not page_is_multicol(pg):
            continue
        text = extract_screenshot_text(pg)
        if not text.strip():
            continue
        # split into per-message blocks at each timestamp header
        idxs = [m.start() for m in TS_RE.finditer(text)]
        if not idxs:
            blocks.append((None, text))
            continue
        if idxs[0] > 0:
            blocks.append((None, text[: idxs[0]].strip()))
        for a, b in zip(idxs, idxs[1:] + [len(text)]):
            chunk = text[a:b].strip()
            blocks.append((ts_key(chunk), chunk))
    doc.close()
    return blocks


def is_screenshot_line(line: str) -> bool:
    """A line that came from a screenshot run: space-collapsed and/or char-salad, not prose."""
    s = line.strip()
    if not s:
        return False
    words = s.split()
    singles = sum(1 for w in words if len(w) == 1)
    longest = max((len(w) for w in words), default=0)
    return singles / len(words) >= 0.30 or longest >= 18 or bool(TS_RE.search(s))


if __name__ == "__main__":
    import sys
    pdf_path = sys.argv[1]
    pages = [int(p) for p in sys.argv[2:]] if len(sys.argv) > 2 else None
    doc = pdfplumber.open(pdf_path)
    for i, pg in enumerate(doc.pages):
        if pages and (i + 1) not in pages:
            continue
        mark = "MULTICOL" if page_is_multicol(pg) else "single"
        print(f"\n===== PAGE {i + 1} [{mark}] {len(pg.images)} images =====")
        print(extract_screenshot_text(pg))
