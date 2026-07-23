#!/usr/bin/env python3
"""
Media step 1 — Factiva PDFs → article- and paragraph-level tables (structure only).

Uses PyMuPDF BLOCKS mode for deterministic paragraph boundaries; splits on each
article's START metadata block, NOT the "Document" end-marker (end-marker splitting
bled paywalled previews into the next article).
Completeness filter drops incomplete records by comparing Factiva-reported length to
recovered body: <STUB_RATIO recovered OR <40 words. The two populations separate
cleanly (full >=80%, previews <10%), so the cutoff is not sensitive/tuned.

Input  : raw_data/Factiva Results/**/*.pdf
Output : media_cleaned_texts/*.txt, media_articles.xlsx, media_paragraphs.xlsx,
         media_filter_audit.csv
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd

ROOT    = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "raw_data" / "Factiva Results"
OUT_DIR = ROOT / "media_cleaned_texts"                            # local only
ARTICLES_OUT   = ROOT / "modified_data" / "media_articles.xlsx"   # local only
PARAGRAPHS_OUT = ROOT / "modified_data" / "media_paragraphs.xlsx"
AUDIT          = ROOT / "media_filter_audit.csv"                  # local only

# Completeness thresholds: below STUB_RATIO of claimed length => paywalled preview.
STUB_MIN_CLAIM = 400
STUB_RATIO     = 0.50
MIN_PARA_WORDS = 5     # drop sub-heads / one-word fragments from the paragraph table

# Block-classification patterns (see classify): metadata line, date, footer, end-marker.
WORDS  = re.compile(r'([\d,]{2,})\s+words', re.IGNORECASE)
DATE   = re.compile(r'\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\b')
FOOTER = re.compile(r'Page\s+\d+\s+of\s+\d+\s+.*Factiva', re.IGNORECASE)
DOCID  = re.compile(r'Document\s+([A-Za-z0-9]{8,})')  # ids have a lowercase suffix


def slugify(text: str, n: int = 28) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', text).strip('_')[:n]


def block_stream(pdf_path: Path) -> list[str]:
    """Ordered list of block texts across all pages (reading order)."""
    doc = fitz.open(pdf_path)
    out = []
    for pno in range(len(doc)):
        for b in sorted(doc[pno].get_text("blocks"), key=lambda b: (round(b[1]), b[0])):
            t = b[4].strip()
            if t:
                out.append(t)
    doc.close()
    return out


def classify(t: str) -> str:
    # meta = article START (words token + date); docid = article END marker.
    if FOOTER.search(t):                          return "footer"
    if DOCID.search(t) and len(t.split()) <= 3:   return "docid"
    if WORDS.search(t) and DATE.search(t):        return "meta"
    return "text"


def split_articles(stream: list[str]) -> list[dict]:
    articles, cur = [], None
    for i, t in enumerate(stream):
        kind = classify(t)
        if kind == "meta":
            # New article starts here; its headline is the block just before it.
            headline = " ".join(stream[i - 1].split()) if i > 0 else ""
            cur = dict(headline=headline,
                       claimed=int(WORDS.search(t).group(1).replace(",", "")),
                       paras=[], docid="", closed=False)
            articles.append(cur)
        elif cur is None:
            continue
        elif kind == "docid":
            cur["docid"] = DOCID.search(t).group(1)
            cur["closed"] = True            # body ends at the Document marker
        elif kind == "text" and not cur["closed"]:
            if t.strip() == cur["headline"]:   # drop the repeated Factiva headline
                continue
            cur["paras"].append(" ".join(t.split()))
    return articles


def status_for(claimed: int, body_words: int, body_text: str) -> str:
    # 4-way cascade: search digest -> paywalled preview -> truncated -> full.
    if "Search Summary" in body_text and body_words < 250:
        return "search_summary"
    if claimed >= STUB_MIN_CLAIM and body_words / max(claimed, 1) < STUB_RATIO:
        return "stub"
    if body_words < 40:
        return "too_short"
    return "full"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for old in OUT_DIR.glob("*.txt"):
        old.unlink()

    pdfs = sorted(PDF_DIR.rglob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs under {PDF_DIR}")

    art_rows, par_rows = [], []
    for pdf_path in pdfs:
        pdf_name = pdf_path.stem
        pdf_slug = slugify(pdf_name, 40)
        # One article table row + its paragraph rows per split article.
        for seq, a in enumerate(split_articles(block_stream(pdf_path)), start=1):
            body_words = sum(len(p.split()) for p in a["paras"])
            body_text  = "\n\n".join(a["paras"])
            status = status_for(a["claimed"], body_words, body_text)
            fname = f"{pdf_slug}__a{seq:03d}__{slugify(a['headline'])}.txt"
            (OUT_DIR / fname).write_text(body_text, encoding="utf-8")

            art_rows.append(dict(
                pdf=pdf_name, seq=seq, filename=fname, headline=a["headline"],
                document_id=a["docid"], claimed_words=a["claimed"],
                actual_words=body_words,
                ratio=round(body_words / a["claimed"], 3) if a["claimed"] else None,
                has_doc_marker=bool(a["docid"]), n_paragraphs=0,
                status=status, is_stub=(status == "stub"), usable=(status == "full"),
            ))

            # Paragraph table excludes sub-head/fragment blocks; recount n_paragraphs.
            kept = [p for p in a["paras"] if len(p.split()) >= MIN_PARA_WORDS]
            art_rows[-1]["n_paragraphs"] = len(kept)
            for pidx, p in enumerate(kept, start=1):
                par_rows.append(dict(
                    pdf=pdf_name, document_id=a["docid"], article_seq=seq,
                    article_filename=fname, headline=a["headline"],
                    article_status=status, article_usable=(status == "full"),
                    para_idx=pidx, para_words=len(p.split()), para_text=p,
                ))

    arts = pd.DataFrame(art_rows)
    pars = pd.DataFrame(par_rows)

    # Cross-search duplicate flag: the same Factiva article appears in >1 search
    # export. Keep every instance (provenance) but flag all-but-first per
    # document_id so article counts can dedupe to unique articles.
    arts["is_duplicate"] = (arts["document_id"].fillna("") != "") & \
                           arts["document_id"].duplicated(keep="first")
    pars = pars.merge(arts[["pdf", "seq", "is_duplicate"]],
                      left_on=["pdf", "article_seq"], right_on=["pdf", "seq"],
                      how="left").drop(columns="seq")

    arts.to_excel(ARTICLES_OUT, index=False)
    arts.to_csv(AUDIT, index=False)
    pars.to_excel(PARAGRAPHS_OUT, index=False)

    print(f"Read {len(pdfs)} PDFs")
    print(f"\nArticles: {len(arts)}")
    print(arts["status"].value_counts().to_string())
    print(f"  usable (full): {int(arts['usable'].sum())}")
    print(f"\nParagraphs (>= {MIN_PARA_WORDS} words): {len(pars)}")
    print(f"  from usable articles: {int(pars['article_usable'].sum())}")
    print(f"  median words/para: {int(pars['para_words'].median())}")
    print(f"\nWrote {ARTICLES_OUT}, {PARAGRAPHS_OUT}, {AUDIT}")


if __name__ == "__main__":
    main()
