# Methods: PhilJobs AI and Phil-tech Job Market Analysis

*Last updated: June 2026. Covers the full data collection, cleaning, classification, and analysis pipeline for the PhilJobs.org AI and philosophy-of-technology job market study (2013–2026).*

---

## Overview of the Pipeline

The analysis proceeds in seven stages, each implemented in a dedicated script:

| Stage | Script | Purpose |
|-------|--------|---------|
| 1 | `philjobs_ai_scraper.py` | Scrape and classify AI-related job ads |
| 2 | `philjobs_ai_details.py` | Fetch full metadata for each AI job |
| 3 | `philjobs_ai_audit.py` | Estimate false-positive and false-negative rates |
| 4 | `philjobs_ai_patch.py` | Remove confirmed false positives; add confirmed false negatives |
| 5 | `philjobs_ai_supplement.py` | Supplementary scrape using expanded keyword list |
| 6 | `normalize_institutions.py` | Clean and canonicalize institution names |
| 7 | `philjobs_philtech_scraper.py` | Scrape phil-tech / STS job ads (initial pass) |
| 8 | `philjobs_philtech_fulltext.py` | Full-page confirmation and recall estimation for phil-tech |
| 9 | `philjobs_ai_plots.R` | Generate all tables and visualizations |

---

## Stage 1 — AI Job Identification (`philjobs_ai_scraper.py`)

### Data source

All data were scraped from PhilJobs.org (formerly *Jobs for Philosophers*), the primary listing service of the American Philosophical Association. Listings were retrieved for January 2013–May 2026 using the site's job query API (`/jobQuery/execute`), requesting all ads per calendar year including expired listings (`withExpired=true`) and paginating in batches of 100.

### Two-pass classification

**Pass 1 — listing-text scan.** For every ad in the paginated results, the visible listing block (job title, AOS, AOC) was checked against a regular-expression pattern covering:

- Case-sensitive standalone tokens: `\bAI\b`, `\bLLM\b`, `\bNLP\b`, `\bGPT\b`
- Case-insensitive phrases: *artificial intelligence*, *machine learning*, *deep learning*, *neural network*, *language model*, *foundation model*, *natural language processing*, *algorithmic bias*, *robotics*, *AI ethics/safety/governance/alignment*, *ethics of AI*, *autonomous system*

**Pass 2 — full-text keyword search.** PhilJobs exposes a full-text search over job descriptions. Each of the following phrases was submitted as a separate query and matching job IDs were added to the candidate set: *artificial intelligence*, *machine learning*, *deep learning*, *neural network*, *large language model*, *language model*, *natural language processing*, *algorithmic bias*, *machine ethics*, *computational intelligence*, *robotics philosophy*, *ethics artificial intelligence*, *autonomous systems*, *foundation model*, *generative model*.

PhilJobs drops query tokens shorter than three characters, so stop words ("of," "and") were omitted from queries. The final AI job set for each year is the union of Pass-1 and Pass-2 results.

### Output

`philjobs_ai_by_year.csv` — one row per year with total ad count, AI job count, proportion, and a pipe-delimited list of AI job IDs.

---

## Stage 2 — Detail Scraping (`philjobs_ai_details.py`)

For each job ID in the AI set, the individual job page (`philjobs.org/job/show/{id}`) was fetched to extract:

- Institution and department (parsed from the `<h2>` element)
- Job title (from `<h1>`)
- Job category, AOS, and location (from structured `<tr class="prop">` fields)

Job categories were standardized using a regex classifier into: *Graduate fellowship*, *Postdoc or similar*, *Visiting/Temp*, *Junior faculty*, *Senior faculty*, *Tenure-track*, *Admin*, *Other/Open*.

### Output

`philjobs_ai_jobs_detail.csv` — one row per confirmed AI job with all extracted metadata.

---

## Stage 3 — Data Quality Audits (`philjobs_ai_audit.py`)

### False-positive audit

A stratified random sample of approximately 6 jobs per year (n ≈ 84 total) was drawn from `philjobs_ai_jobs_detail.csv`. Each job page was re-fetched and checked against a broad AI verification regex that is deliberately wider than the original scraper (adding newer terminology: *transformer model*, *ChatGPT*, *GPT-4*, *RLHF*, *AI alignment*, etc.). Jobs for which no AI-related term was found on the current page were flagged as candidate false positives.

This procedure identified two institutional clusters — Wake Forest University (15 ads) and Minerva Schools at KGI (3 ads) — plus 9 individual false positives, for 27 total removals. The estimated residual false-positive rate after correction is approximately 11% (95% Wilson CI: 6–19%).

### False-negative audit

The sample of non-AI-flagged jobs collected during the phil-tech recall analysis (`philjobs_philtech_sample.csv`, 50 non-flagged jobs per year × 14 years = 643 jobs after excluding known AI IDs) was checked with the same broad AI verification regex. Fourteen jobs (2.2%; 95% CI: 1.3–3.6%) matched AI-related terms and were confirmed as false negatives. The estimated residual false-negative rate is approximately 2% (95% CI: 1–4%).

---

## Stage 4 — Dataset Patch (`philjobs_ai_patch.py`)

**Part A.** All Minerva Schools jobs were re-fetched and verified. Those with no AI content on the current page were removed from `philjobs_ai_jobs_detail.csv` and `philjobs_ai_by_year.csv`.

**Part B.** The 14 confirmed false-negative jobs were fetched and, after verifying AI content still appeared on the page, their metadata was extracted and added to the dataset. Both output CSVs were updated accordingly.

---

## Stage 5 — Supplementary Scrape (`philjobs_ai_supplement.py`)

A targeted supplementary scrape was run using six keywords not present in the original scraper: *language model*, *robotics philosophy*, *ethics artificial intelligence*, *autonomous systems*, *foundation model*, *generative model*. For each year, all job IDs returned by these queries that were not already in the dataset were fetched and verified against the broad AI regex. Confirmed matches were added to both CSVs. This recovered 18 additional confirmed AI jobs.

---

## Stage 6 — Institution Normalization (`normalize_institutions.py`)

Institution names extracted from PhilJobs contained several systematic artifacts:

1. **Partial names** — the `<h2>` parsing algorithm captured only the last comma-delimited segment for multi-campus institutions (yielding "Hong Kong," "Madison," "Sweden," etc.). These were resolved by re-fetching the structured institution field from the job page.
2. **Encoding artifacts** — non-ASCII characters produced garbled strings (e.g., "Ume? University"). These were corrected via a replacement mapping.
3. **Name variants** — several institutions appeared under multiple spellings (e.g., "Technical University of Eindhoven" vs. "Eindhoven University of Technology"; "Oxford" vs. "University of Oxford"). Variants were merged to a canonical form.
4. **Spurious suffixes** — "not BA-granting" annotations were stripped from institution names.

After normalization, the dataset covers institutions from 37 countries.

---

## Stage 7 — Phil-tech / STS Initial Scrape (`philjobs_philtech_scraper.py`)

The same two-pass strategy was applied to identify philosophy-of-technology and STS job ads.

### Pass 1 regex (listing text)

Covers: *philosophy of technology/technological*, *post-phenomenology*, `\bSTS\b`, *science and technology studies*, *technology studies*, *philosophy of media*, *philosophy of engineering*, *critical technology/technologies*, *empirical turn*, *phil. of tech* (abbreviated forms), *ethics of technology*, *digital ethics*, *philosophy of computing*, *sociotechnical*, *technoscience*.

### Pass 2 keyword searches

Phrases submitted to PhilJobs full-text search: *technology studies*, *science technology studies*, *critical technologies*, *empirical turn*, *philosophy technology ethics*, *sociotechnical*, *technoscience*, *digital ethics*, *philosophy computing*, *ethics technology*.

The union of Pass-1 and Pass-2 results was cross-referenced against the AI job ID set to produce four groups per year: *phil-tech only*, *phil-tech and AI*, *AI only*, *neither*.

### Keyword expansion (June 2026)

To reduce the recall uncertainty band in Plot 8A, the Pass-1 regex and Pass-2 keyword list were expanded to add: *ethics of technology*, *digital ethics*, *philosophy of computing*, *sociotechnical*, *technoscience*, *ethics technology*. The full-text regex in Stage 8 was simultaneously expanded with: *responsible innovation*, *values in design* / *VSD*, *philosophy of information technology*. The dataset was regenerated in full following this expansion.

---

## Stage 8 — Phil-tech Full-text Confirmation and Recall Estimation (`philjobs_philtech_fulltext.py`)

Because Pass-1 listing-text matching operates on a short visible block rather than the full description, it carries recall risk. This stage provides both a precision check on Pass-1 hits and a recall estimate from a sample of non-hits.

### Stage 1 — Listing scan

All ads for the year are paginated. IDs matching the listing regex are collected as Pass-1 candidates; all other IDs encountered form the non-hit pool.

### Stage 2a — Pass-1 confirmation

Each Pass-1 job page is fetched in full and checked against an expanded full-text regex that adds: *technoscience*, *actor-network theory*, *value-sensitive design*, *philosophy of design*, *philosophy of artifacts*, `\bSPT\b` (Society for Philosophy and Technology), *philosophy of infrastructure*, *sociotechnical/socio-technical*, *ethics of technology*, *digital ethics*, *philosophy of computing*, *responsible innovation*, *values in design* / `\bVSD\b`, *philosophy of information technology*. Only jobs confirmed by full-text matching are counted in the final dataset.

### Stage 2b — Recall estimation sample

50 non-Pass-1 job IDs are drawn at random per year and their full pages are fetched and checked with the same full-text regex. The fraction that match phil-tech terms is the *sample hit rate*.

### Stage 3 — Recall-adjusted estimates

The sample hit rate is applied to the total number of non-Pass-1 ads to estimate how many phil-tech jobs were missed. A 95% Wilson confidence interval on the hit rate is propagated to produce lower and upper bounds on the estimated true count (`recall_lower`, `recall_upper`). These bounds are the source of the green uncertainty ribbon in Plot 8A.

The confirmed Pass-1 count (`pass1_confirmed`) is used as the conservative lower bound in all cross-referencing with AI job IDs.

### Output

- `philjobs_philtech_confirmed.csv` — one row per job page fetched in Stage 2a/2b with confirmation result
- `philjobs_philtech_sample.csv` — sample audit results used for recall estimation and reused by the AI false-negative audit
- `philjobs_philtech_final.csv` — per-year four-group counts with recall-adjusted estimates and CI bounds

---

## Stage 9 — Visualization (`philjobs_ai_plots.R`)

All tables and plots are generated from `philjobs_ai_plots.R` using R 4.5.2 with the `tidyverse`, `scales`, `knitr`, `kableExtra`, and `glue` packages. The script reads from:

- `philjobs_ai_by_year.csv` — annual AI counts
- `philjobs_ai_jobs_detail.csv` — per-job metadata for AOS and contract-type analyses
- `philjobs_philtech_final.csv` — phil-tech counts and recall bounds for Plot 8A

Plots are saved as PNG files at 150 dpi to the `plots/` subdirectory. Input CSV paths are specified as absolute paths via a `data_dir` variable at the top of the script to ensure portability across working directories.

---

## AOS Classification

Two parallel AOS classification systems were developed:

**Python (`analyze_aos.py`)** — a multi-label keyword classifier applied to the raw AOS strings in `philjobs_ai_jobs_detail.csv`. Categories: *Ethics/Applied Ethics*, *Phil. of Mind/Cog. Sci./AI*, *Logic/Formal Methods*, *Epistemology*, *Phil. of Science/Technology*, *Social/Political Philosophy*, *Metaphysics/Ontology*, *History/Continental/Non-Western*, *Philosophy of Language*, *Open/Unspecified*, *Other/Unclassified*.

**R (`philjobs_ai_plots.R`, Section 7)** — a refined multi-label classifier that separates *Phil. of Science* from *Phil. of Technology* using a combination of explicit keyword patterns and a residual catch (`technolog` in AOS without `science`). This classifier is used for all plots in the analysis.

---

## Statistical Methods

**Wilson confidence intervals** are used throughout for proportions estimated from small samples (false-positive rate, false-negative rate, phil-tech recall rate). The Wilson interval is preferred over the normal approximation because it performs well near the boundaries (0 and 1) and with small sample sizes.

The formula used:

$$\hat{p}_{\pm} = \frac{\hat{p} + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

where $z = 1.96$ for 95% intervals, $\hat{p}$ is the observed proportion, and $n$ is the sample size.

**Recall-adjusted counts** are computed as: confirmed count + round(sample hit rate × number of non-flagged ads). The confidence interval on the hit rate is propagated to give `recall_lower` and `recall_upper` by applying the CI bounds to the non-flagged pool and adding the confirmed count.

---

## Rate-limiting and Reproducibility

All scraping scripts include deliberate rate-limiting (0.6–0.8 seconds between requests) to avoid overloading PhilJobs.org. Scripts implement resume logic: years already present in output CSVs are skipped, allowing safe interruption and restart. The random seed `42` is used for recall-estimation samples and `99` for false-positive audit samples, ensuring reproducibility.

---

*Source: PhilJobs.org. Scripts: philjobs\_ai\_scraper.py, philjobs\_ai\_details.py, philjobs\_ai\_audit.py, philjobs\_ai\_patch.py, philjobs\_ai\_supplement.py, normalize\_institutions.py, philjobs\_philtech\_scraper.py, philjobs\_philtech\_fulltext.py, philjobs\_ai\_plots.R.*
