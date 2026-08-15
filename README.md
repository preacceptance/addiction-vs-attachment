# Data & Code for "'Addiction' Is An Incomplete Framework For Understanding Conversational AI Dependency"

## Run

```bash
# To compute the paper's statistics
Rscript code/compute_paper_stats.R

# To rescore inter-rater reliability against the frozen coded workbooks
python3 code/score_irr_24.py
python3 code/build_v9_review.py

# To re-draw both IRR samples and verify them against the stored manifests
python3 code/draw_irr_samples.py

# To reproduce the coding pipeline (requires an OpenAI API key)
# Legal
python3 code/legal_surface_24.py                 # surface-level analysis
RUN_TAG=_v9p1 python3 code/legal_llm_24.py       # deeper-level analysis, pass 1 (seed 1)
RUN_TAG=_v9p2 python3 code/legal_llm_24.py       # deeper-level analysis, pass 2 (seed 2; reported)
python3 code/within_llm_kappa_24.py              # reliability between the two passes
python3 code/legal_figures.py                    # figures

# Media
python3 code/media_surface_24.py                 # surface-level analysis
RUN_TAG=_v9p1 python3 code/media_llm_24.py       # deeper-level analysis, pass 1 (seed 1)
RUN_TAG=_v9p2 python3 code/media_llm_24.py       # deeper-level analysis, pass 2 (seed 2; reported)
python3 code/media_within_llm_kappa_24.py        # reliability between the two passes
python3 code/media_figures.py                    # figures
```

Run from the project root with an OpenAI key in `.env` (`OPENAI_API_KEY=...`).

## Files

```
.
├── README.md
├── Coding_Instructions_v9_Legal_final.docx   coding manual (legal)
├── Coding_Instructions_v9_Media_final.docx   coding manual (media)
├── code/
│   ├── bake_manuals_v9.py                    rebuilds the LLM prompts from the two manuals
│   │                                         (verifies they differ only in title and genre intro)
│   ├── legal_surface_24.py                   legal surface (vocabulary) coding
│   ├── media_surface_24.py                   media surface (vocabulary) coding
│   ├── legal_llm_24.py                       legal deeper (LLM) coding, seeded two-pass
│   ├── media_llm_24.py                       media deeper (LLM) coding, seeded two-pass
│   ├── within_llm_kappa_24.py                legal pass-1 vs pass-2 reliability
│   ├── media_within_llm_kappa_24.py          media pass-1 vs pass-2 reliability
│   ├── draw_irr_samples.py                   re-draws both stratified IRR samples (seeded)
│   ├── build_irr_sheets.py                   builds the blind rating workbooks
│   ├── score_irr_24.py                       human-consensus vs LLM reliability
│   ├── build_v9_review.py                    rescores reliability for the revised manual
│   ├── build_disagreement_html.py            renders rater-disagreement review pages
│   ├── figures_common.py                     shared figure helpers
│   ├── legal_figures.py                      legal figures
│   ├── media_figures.py                      media figures
│   ├── compute_paper_stats.R                 all statistics reported in the paper
│   ├── paper_stats_output.txt                its output: the paper's numbers ledger
│   └── (dictionary_pass.py, media_dictionary_pass.py,
│        llm_pass_v2.py, procedural_attach.py) earlier-version helpers kept for reference
├── modified_data/                            coded paragraph corpora, few-shot grids,
│                                             rater workbooks, IRR sample manifests
├── output/                                   surface- and LLM-coded corpora, scored reliability
└── figures/                                  manuscript and supplementary figures
```

Raw source data (court complaint PDFs and licensed news-database exports) and the
extraction code that converts them into the paragraph workbooks are available upon
request. They are required only to rebuild the paragraph corpora from scratch; all
analyses above run from the workbooks included here.
