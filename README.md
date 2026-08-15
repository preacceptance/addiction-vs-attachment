# Data & Code for "Addiction Is An Incomplete Framework For Understanding Conversational AI Dependency"



## Run

```bash
# To compute the paper's statistics (writes code/paper_stats_output.txt)
Rscript code/compute_paper_stats.R

# To reproduce the entire pipeline (requires OpenAI API key)
# Legal
python3 code/legal_surface_24.py               # surface-level analysis
python3 code/legal_llm_24.py                   # deeper-level analysis
python3 code/legal_figures.py                  # create figures

# Media
python3 code/media_surface_24.py               # surface-level analysis
python3 code/media_llm_24.py                   # deeper-level analysis
python3 code/media_figures.py                  # create figures
```

Run from the project root with an OpenAI key in `.env` (`OPENAI_API_KEY=...`).

## Files

```
.
├── README.md
├── Coding_Instructions_v9_Legal_final.docx   coding manual (legal)
├── Coding_Instructions_v9_Media_final.docx   coding manual (media)
├── code/
│   ├── bake_manuals_v9.py                    turns instruction docx files into LLM prompts
│   ├── legal_surface_24.py                   legal surface (vocabulary) coding
│   ├── media_surface_24.py                   media surface (vocabulary) coding
│   ├── legal_llm_24.py                       legal deeper (LLM) coding
│   ├── media_llm_24.py                       media deeper (LLM) coding
│   ├── within_llm_kappa_24.py                legal pass-1 vs pass-2 within-LLM reliability
│   ├── media_within_llm_kappa_24.py          media pass-1 vs pass-2 within-LLM reliability
│   ├── draw_irr_samples.py                   stratified IRR sample draws
│   ├── score_irr_24.py                       human vs LLM reliability
│   ├── compute_paper_stats.R                 paper stats
│   ├── figures_common.py                     shared figure helpers
│   ├── legal_figures.py                      legal figures
│   └── media_figures.py                      media figures
├── modified_data/                            paragraph spreadsheets, coding sheets, few-shots
├── output/                                   LLM-coded corpora, scored reliability
└── figures/                                  manuscript and supplementary figures
```

Raw source data is available upon request. It is required to rebuild the
paragraph spreadsheets from scratch; all analyses above run from the
spreadsheets included here.
