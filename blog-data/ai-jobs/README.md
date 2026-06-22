# AI and jobs in academic philosophy — data and reproducible pipeline

Data, code, and methods behind the blog post
[**AI and jobs in academic philosophy**](../../posts/ai-and-jobs-in-academic-philosophy.html)
(2 June 2026), a study of AI-related and philosophy-of-technology job ads on
[PhilJobs.org](https://philjobs.org) from January 2013 to May 2026.

Everything needed to regenerate the figures and tables in the post is in this
folder. For the full prose write-up of the methodology, see
[`philjobs_methods.md`](philjobs_methods.md).

---

## What's here

### Data sets (CSV)

| File | Rows | Description |
|------|------|-------------|
| `philjobs_ai_jobs_detail.csv` | 667 | **Main dataset.** One row per confirmed AI job ad, with institution, department, title, job category, AOS, location, and year. |
| `philjobs_ai_by_year.csv` | 14 | Annual totals: all ads, AI ads, AI proportion, and the pipe-delimited AI job IDs per year. |
| `philjobs_ai_institutions.csv` | 289 | AI ad counts per institution, ranked. |
| `philjobs_ai_job_types.csv` | 8 | AI ad counts by standardized job category. |
| `philjobs_ai_audit_fp.csv` | 84 | False-positive audit sample (re-fetched and re-checked). |
| `philjobs_ai_audit_fn.csv` | 643 | False-negative audit sample. |
| `philjobs_philtech_by_year.csv` | 14 | Phil-tech / STS counts per year, cross-referenced with AI ads. |
| `philjobs_philtech_confirmed.csv` | 208 | Full-text-confirmed phil-tech job IDs. |
| `philjobs_philtech_sample.csv` | 700 | Recall-estimation sample (also reused by the AI false-negative audit). |
| `philjobs_philtech_final.csv` | 14 | Per-year four-group counts with recall-adjusted estimates and 95% CI bounds (the green ribbon in Plot 8A). |

#### Main dataset columns (`philjobs_ai_jobs_detail.csv`)

`job_id`, `year`, `institution`, `department`, `job_title`, `job_category` (raw),
`std_category` (standardized: *Graduate fellowship*, *Postdoc or similar*,
*Visiting/Temp*, *Junior faculty*, *Senior faculty*, *Tenure-track*, *Admin*,
*Other/Open*), `aos` (area of specialization, free text — ads may list several),
`location`.

### Code (the pipeline)

| Stage | Script | Language | Reads → Writes |
|-------|--------|----------|----------------|
| 1 | `philjobs_ai_scraper.py` | Python | PhilJobs.org → `philjobs_ai_by_year.csv` |
| 2 | `philjobs_ai_details.py` | Python | `philjobs_ai_by_year.csv` → `philjobs_ai_jobs_detail.csv` |
| 3 | `philjobs_ai_audit.py` | Python | dataset → `philjobs_ai_audit_fp.csv`, `philjobs_ai_audit_fn.csv` |
| 4 | `philjobs_ai_patch.py` | Python | removes confirmed false positives, adds false negatives |
| 5 | `philjobs_ai_supplement.py` | Python | supplementary scrape with expanded keywords |
| 6 | `normalize_institutions.py` | Python | canonicalizes institution names |
| 7 | `philjobs_philtech_scraper.py` | Python | PhilJobs.org → `philjobs_philtech_by_year.csv` |
| 8 | `philjobs_philtech_fulltext.py` | Python | full-text confirmation → `philjobs_philtech_confirmed.csv`, `_sample.csv`, `_final.csv` |
| 9 | `philjobs_ai_plots.R` | R | the CSVs above → all figures/tables in `plots/` |

`analyze_aos.py` is a supplementary Python keyword classifier for areas of
specialization; the AOS plots in the post use the refined R classifier built into
`philjobs_ai_plots.R` (Section 7).

---

## Reproducing the analysis

### Just the figures and tables (no scraping)

The CSVs in this folder are the post-audit, cleaned outputs, so you can skip
straight to Stage 9:

```r
# R 4.5.2; from inside this folder
install.packages(c("tidyverse", "scales", "knitr", "kableExtra", "glue"))
setwd("path/to/blog-data/ai-jobs")
source("philjobs_ai_plots.R")   # writes PNGs to ./plots/
```

`philjobs_ai_plots.R` reads its inputs from `data_dir <- "."`, so run R with this
folder as the working directory.

### Rebuilding the dataset from scratch (re-scraping PhilJobs)

```bash
# Python 3.11+; from inside this folder
pip install requests beautifulsoup4 pandas
python philjobs_ai_scraper.py        # Stage 1
python philjobs_ai_details.py        # Stage 2
python philjobs_ai_audit.py          # Stage 3
python philjobs_ai_patch.py          # Stage 4
python philjobs_ai_supplement.py     # Stage 5
python normalize_institutions.py     # Stage 6
python philjobs_philtech_scraper.py  # Stage 7
python philjobs_philtech_fulltext.py # Stage 8
# then Stage 9 in R, as above
```

The Python scripts read and write their CSVs from their own folder
(`Path(__file__).parent`), so no path editing is needed.

---

## Notes and caveats

- **Live scraping.** Stages 1–8 fetch from PhilJobs.org. Re-running them will
  reflect the site's current contents and may differ slightly from the committed
  CSVs as listings expire or are edited. The scrapers rate-limit (0.6–0.8 s
  between requests) and resume safely — years already present in an output CSV are
  skipped, so an interrupted run can be restarted.
- **Random seeds.** Seed `42` is used for recall-estimation samples and `99` for
  the false-positive audit, so the sampling steps are reproducible.
- **Measurement uncertainty.** After the audits, the AI counts carry roughly
  ±10–15% per-year uncertainty (≈11% residual false positives, ≈2% residual false
  negatives); the directional trend is robust. Phil-tech counts are a
  100%-precision lower bound with a Wilson-interval recall band — see Plot 8A and
  `philjobs_methods.md` for how to read them.
- **Coverage.** PhilJobs is the main listing service for the English-speaking
  philosophy world; non-English job markets are not represented. After
  normalization the data span institutions in 37 countries.
- **Source.** PhilJobs.org (American Philosophical Association). The 2026 column
  is partial (through May 2026).

---

## Known discrepancies

**Plot 1 counts vs. `philjobs_ai_by_year.csv`.** The headline AI-proportion chart
(Plot 1, the "≈1% → 16%" figure in the post) is drawn from an annual table
hard-coded in `philjobs_ai_plots.R` (the `annual` tribble near the top), *not*
from `philjobs_ai_by_year.csv`. That hard-coded table reflects an earlier cut of
the data, taken before the supplementary scrape and false-negative patch added a
few more confirmed AI ads per year. The yearly **totals** agree; the **AI counts**
in the CSV run a few higher than the plotted figures:

| Year | `by_year.csv` AI ads | Plot 1 (hard-coded) AI ads |
|------|----------------------|-----------------------------|
| 2023 | 100 | 91 |
| 2024 | 96  | 91 |
| 2025 | 94  | 86 |
| 2026 | 51  | 48 |

Consequences:

- Re-running `philjobs_ai_plots.R` reproduces the post's Plot 1 exactly, because
  the numbers are baked into the script.
- `philjobs_ai_by_year.csv` is the **final, post-audit** dataset and is the count
  to cite; it implies a slightly higher 2025 share (94/536 ≈ 17.5%) than the
  post's stated 16%.
- The detailed dataset `philjobs_ai_jobs_detail.csv` (667 rows) is consistent with
  the CSV annual counts, not with the hard-coded table.

To make the plot read straight from the data, replace the `annual` tribble in
`philjobs_ai_plots.R` with a `read_csv("philjobs_ai_by_year.csv")` of
`year`, `total_jobs`, and `ai_jobs`; note this shifts Plot 1's later years upward
and would warrant updating the "16%" / "1-in-6" phrasing in the post.

---

If you'd like to collaborate — especially on non-English job markets or cleaning
the AOS field — please [get in touch](mailto:charles.lassiter@gmail.com).
