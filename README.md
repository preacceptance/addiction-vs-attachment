# Data & Code for "Addiction Is An Incomplete Framework For Understanding Conversational AI Dependency"



## Run

```bash
# To compute the paper's statistics
python3 code/compute_irr_v7.py
Rscript  code/compute_paper_stats.R

# To reproduce the entire pipeline (Requires OpenAI API key)
# Legal
python3 code/dictionary_pass.py  # surface-level analysis 
python3 code/llm_pass_v2.py      # deeper-level analysis
python3 code/legal_figures.py    #create figures

# media
python3 code/media_dictionary_pass.py # surface-level analysis
python3 code/media_llm_pass.py        # deeper-level analysis
python3 code/media_figures.py         # create figures 

```

Run from the project root with an OpenAI key in `.env` (`OPENAI_API_KEY=...`).

## Files

```
.
├── README.md
├── Coding_Instructions_v7_Legal_Final.docx   coding manual (legal)
├── Coding_Instructions_v7_Media_Final.docx   coding manual (media)
├── code/
│   ├── extract_paragraphs.py                 legal text  -> paragraphs
│   ├── media_extract.py                      Factiva PDFs -> paragraphs
│   ├── dictionary_pass.py                    legal surface (vocabulary) coding
│   ├── media_dictionary_pass.py              media surface (vocabulary) coding
│   ├── procedural_attach.py                  helper: removing unrelated mentions of "attach*"
│   ├── llm_pass_v2.py                        legal deeper (LLM) coding
│   ├── media_llm_pass.py                     media deeper (LLM) coding
│   ├── compute_irr_v7.py                     human vs LLM reliability
│   ├── compute_paper_stats.R                 paper stats 
│   ├── figures_common.py                     shared figure helpers
│   ├── legal_figures.py                      legal figures
│   ├── media_figures.py                      media figures
│   ├── make_pipeline_figure.py               workflow schematic
│   ├── dev/                                  one-off scripts
│   └── archive/                              older scripts
├── modified_data/                            paragraph spreadsheets, coding sheets, few-shots
├── output/                                   LLM-coded corpora, scored reliability
└── figures/                                  manuscript and supplementary figures
```

Raw source data is available upon request. It is required to recompute the surface and deeper-level codes from scratch. 
