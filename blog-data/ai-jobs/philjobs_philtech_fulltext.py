"""
philjobs_philtech_fulltext.py

Accurate phil-tech / STS job detection via full-page text scraping.

Stage 1  Paginate all PhilJobs listings (Pass 1):
         - Collect IDs whose listing text (title + AOS/AOC) matches a
           phil-tech regex  →  candidate set
         - Collect a stratified random sample of non-matching IDs
           →  used to estimate recall (false-negative rate)

Stage 2  Fetch individual job pages:
         a) All Pass-1 IDs  →  confirm against full page text
         b) Sampled non-Pass-1 IDs  →  detect false negatives

Stage 3  Per-year recall-adjusted counts; cross-reference with AI job IDs
         from philjobs_ai_by_year.csv  →  four groups
         (phil_tech_only, phil_tech_and_ai, ai_only, neither)

Intermediate results are saved after each year so the script can be
safely interrupted and resumed.

Outputs
  philjobs_philtech_confirmed.csv   confirmed phil-tech job IDs + year
  philjobs_philtech_sample.csv      sample audit results
  philjobs_philtech_final.csv       per-year four-group counts
"""

import csv
import random
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# ── File paths ────────────────────────────────────────────────────────────────

BASE_DIR     = Path(__file__).parent
AI_CSV       = BASE_DIR / "philjobs_ai_by_year.csv"
CONFIRMED_CSV = BASE_DIR / "philjobs_philtech_confirmed.csv"
SAMPLE_CSV   = BASE_DIR / "philjobs_philtech_sample.csv"
FINAL_CSV    = BASE_DIR / "philjobs_philtech_final.csv"

BASE_URL   = "https://philjobs.org/jobQuery/execute"
JOB_URL    = "https://philjobs.org/job/show/"
YEARS      = list(range(2013, 2027))
SAMPLE_N   = 50   # non-Pass-1 jobs to fetch per year for recall estimation

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

random.seed(42)   # reproducible samples


# ── Regexes ───────────────────────────────────────────────────────────────────

# Pass 1: applied to the short listing-text block (title + AOS/AOC).
# Word-boundary matching; low false-positive rate.
LISTING_RE = re.compile(
    r"""
    philosophy\s+of\s+technolog         # philosophy of technology / technological
    | post[- ]?phenomenolog             # post-phenomenology / postphenomenology
    | \bSTS\b                           # STS acronym
    | science\s+and\s+technology\s+stud # science and technology studies
    | \btechnology\s+studies\b          # technology studies (standalone)
    | philosophy\s+of\s+media           # philosophy of media
    | philosophy\s+of\s+engineering     # philosophy of engineering
    | \bcritical\s+technolog            # critical technology / technologies
    | \bempirical\s+turn\b              # the empirical turn (classic phil-tech)
    | \bphil\w*\.\s*of\s+tech\b        # abbreviated "phil. of tech"
    | ethics\s+of\s+technolog           # ethics of technology (common European phrasing)
    | \bdigital\s+ethics\b              # digital ethics (post-2018 growth field)
    | philosophy\s+of\s+computing       # philosophy of computing
    | sociotechnical                    # sociotechnical (STS core term)
    | technoscience                     # technoscience (STS term)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Full-text: applied to the complete job page.
# Broader — includes STS-specific vocabulary and key theoretical terms.
FULLTEXT_RE = re.compile(
    r"""
    philosophy\s+of\s+technolog
    | post[- ]?phenomenolog
    | \bSTS\b
    | science\s+and\s+technology\s+stud
    | \btechnology\s+studies\b
    | philosophy\s+of\s+media
    | philosophy\s+of\s+engineering
    | \bcritical\s+technolog
    | \bempirical\s+turn\b
    | technoscience                     # technoscience (STS term)
    | actor[- ]?network                 # actor-network theory (ANT)
    | \bvalue.sensitive\s+design\b      # value-sensitive design
    | philosophy\s+of\s+design
    | philosophy\s+of\s+artifacts?
    | \bSPT\b                           # Society for Philosophy and Technology
    | philosophy\s+of\s+infrastructure
    | sociotechnical
    | socio.technical
    | ethics\s+of\s+technolog           # ethics of technology (common European phrasing)
    | \bdigital\s+ethics\b              # digital ethics (post-2018 growth field)
    | philosophy\s+of\s+computing       # philosophy of computing
    | responsible\s+innovation          # responsible innovation (STS term)
    | values?\s+in\s+design             # values in design / value in design (VSD tradition)
    | \bVSD\b                           # value sensitive design acronym
    | philosophy\s+of\s+information\s+technolog  # philosophy of information technology
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def make_params(year, offset=0):
    end_month = 5 if year == 2026 else 12
    return {
        "jobQuery.fromDate_day":   "1",
        "jobQuery.fromDate_month": "1",
        "jobQuery.fromDate_year":  str(year),
        "jobQuery.toDate_day":     "31",
        "jobQuery.toDate_month":   str(end_month),
        "jobQuery.toDate_year":    str(year),
        "withExpired":             "true",
        "format":                  "",
        "create":                  "Search",
        "jobQuery.orderBy":        "DATE",
        "withStubs":               "true",
        "withExcluded":            "true",
        "withSaved":               "true",
        "jobQuery.keywords":       "",
        "offset":                  str(offset),
        "max":                     "100",
    }


def fetch_listing_page(session, params, retries=3):
    """Return (total_count, {job_id: listing_text})."""
    for attempt in range(retries):
        try:
            r = session.get(BASE_URL, params=params, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            total = 0
            for el in soup.find_all(True):
                m = re.search(r"found\s+([\d,]+)\s+ads", el.get_text(strip=True), re.I)
                if m:
                    total = int(m.group(1).replace(",", ""))
                    break

            jobs = {}
            seen = set()
            for a in soup.find_all("a", href=True):
                m = re.match(r"/job/show/(\d+)$", a["href"])
                if not m:
                    continue
                job_id = int(m.group(1))
                if job_id in seen:
                    continue
                seen.add(job_id)
                block_text = ""
                parent = a
                for _ in range(12):
                    parent = parent.parent
                    if parent is None:
                        break
                    t = parent.get_text(separator=" ", strip=True)
                    if "AOS:" in t or "AOC:" in t:
                        block_text = t
                        break
                jobs[job_id] = block_text

            return total, jobs

        except requests.RequestException as e:
            print(f"    Listing page error (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return 0, {}


def fetch_job_text(session, job_id, retries=3):
    """Fetch a job page; return full visible text, or None on failure."""
    url = f"{JOB_URL}{job_id}"
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            return soup.get_text(separator=" ", strip=True)
        except requests.RequestException as e:
            print(f"    Job {job_id} error (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(4)
    return None


# ── Stage 1: Pass 1 listing scan ─────────────────────────────────────────────

def stage1_collect_ids(session, year):
    """
    Paginate all ads for the year.
    Returns:
      total        – reported ad count
      pass1_ids    – set of IDs matching LISTING_RE
      all_seen_ids – set of all IDs encountered during pagination
    """
    pass1_ids    = set()
    all_seen_ids = set()
    offset       = 0
    total        = None

    while True:
        params = make_params(year, offset=offset)
        page_total, jobs = fetch_listing_page(session, params)
        time.sleep(0.8)

        if total is None:
            total = page_total

        for job_id, listing_text in jobs.items():
            all_seen_ids.add(job_id)
            if LISTING_RE.search(listing_text):
                pass1_ids.add(job_id)

        if not jobs or (total and offset + 100 >= total):
            break
        offset += 100

    return total or 0, pass1_ids, all_seen_ids


# ── Stage 2: fetch individual pages ──────────────────────────────────────────

def stage2_fetch_and_classify(session, job_ids, label, year):
    """
    Fetch full page for each job_id; classify with FULLTEXT_RE.
    Returns list of dicts: {job_id, year, source, is_philtech, fetch_ok}
    """
    results = []
    n = len(job_ids)
    for i, job_id in enumerate(sorted(job_ids), 1):
        if i % 20 == 0:
            print(f"    [{label}] {i}/{n}...")
        text = fetch_job_text(session, job_id)
        is_philtech = bool(FULLTEXT_RE.search(text)) if text else False
        results.append({
            "job_id":      job_id,
            "year":        year,
            "source":      label,
            "is_philtech": is_philtech,
            "fetch_ok":    text is not None,
        })
        time.sleep(0.6)
    return results


# ── Load AI job IDs ───────────────────────────────────────────────────────────

def load_ai_data():
    ai = {}
    if not AI_CSV.exists():
        print(f"WARNING: {AI_CSV} not found.")
        return ai
    with open(AI_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yr   = int(row["year"])
            tot  = int(row["total_jobs"])
            ids  = set()
            for jid in (row.get("ai_job_ids") or "").split("|"):
                if jid.strip():
                    ids.add(int(jid))
            ai[yr] = (tot, ids)
    return ai


# ── Resume helpers ────────────────────────────────────────────────────────────

def load_done_years(csv_path):
    """Return set of years already written to an output CSV."""
    done = set()
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(int(row["year"]))
    return done


def append_rows(csv_path, fieldnames, rows):
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerows(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ai_data = load_ai_data()
    session = requests.Session()
    session.headers.update(HEADERS)

    # Skip years already fully processed
    done_confirmed = load_done_years(CONFIRMED_CSV)
    done_sample    = load_done_years(SAMPLE_CSV)
    done_final     = load_done_years(FINAL_CSV)

    confirmed_fields = ["job_id", "year", "source", "is_philtech", "fetch_ok"]
    sample_fields    = ["job_id", "year", "source", "is_philtech", "fetch_ok"]
    final_fields     = [
        "year", "total_jobs", "pass1_ids", "pass1_confirmed",
        "sample_n", "sample_hits", "estimated_missed",
        "estimated_philtech", "ai_jobs",
        "philtech_and_ai", "philtech_only", "ai_only", "neither",
        "recall_lower", "recall_upper",
    ]

    summary_rows = []

    for year in YEARS:
        print(f"\n{'=' * 65}")
        print(f"Year: {year}")

        # ── Stage 1 ──────────────────────────────────────────────────────────
        print("  Stage 1: scanning all listings...")
        total, pass1_ids, all_seen_ids = stage1_collect_ids(session, year)
        non_pass1_ids = all_seen_ids - pass1_ids
        print(f"  Total ads: {total}  |  Pass 1 hits: {len(pass1_ids)}  "
              f"|  Non-hits seen: {len(non_pass1_ids)}")

        # Draw reproducible sample
        sample_ids = set(random.sample(
            sorted(non_pass1_ids),
            min(SAMPLE_N, len(non_pass1_ids))
        ))

        # ── Stage 2a: confirm Pass-1 hits ────────────────────────────────────
        if year not in done_confirmed:
            print(f"  Stage 2a: confirming {len(pass1_ids)} Pass-1 jobs...")
            confirmed_rows = stage2_fetch_and_classify(
                session, pass1_ids, "pass1", year)
            append_rows(CONFIRMED_CSV, confirmed_fields, confirmed_rows)
        else:
            print(f"  Stage 2a: already done, loading from {CONFIRMED_CSV}...")
            confirmed_rows = []
            with open(CONFIRMED_CSV, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["year"]) == year:
                        row["is_philtech"] = row["is_philtech"] == "True"
                        row["fetch_ok"]    = row["fetch_ok"]    == "True"
                        confirmed_rows.append(row)

        # ── Stage 2b: sample non-Pass-1 jobs ─────────────────────────────────
        if year not in done_sample:
            print(f"  Stage 2b: fetching {len(sample_ids)}-job sample...")
            sample_rows = stage2_fetch_and_classify(
                session, sample_ids, "sample", year)
            append_rows(SAMPLE_CSV, sample_fields, sample_rows)
        else:
            print(f"  Stage 2b: already done, loading from {SAMPLE_CSV}...")
            sample_rows = []
            with open(SAMPLE_CSV, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if int(row["year"]) == year:
                        row["is_philtech"] = row["is_philtech"] == "True"
                        row["fetch_ok"]    = row["fetch_ok"]    == "True"
                        sample_rows.append(row)

        # ── Stage 3: recall-adjusted estimates ───────────────────────────────
        n_pass1          = len(pass1_ids)
        n_confirmed      = sum(1 for r in confirmed_rows
                               if r["is_philtech"] and r["fetch_ok"])
        n_sample         = sum(1 for r in sample_rows if r["fetch_ok"])
        n_sample_hits    = sum(1 for r in sample_rows
                               if r["is_philtech"] and r["fetch_ok"])
        n_non_pass1_seen = len(non_pass1_ids)

        hit_rate = n_sample_hits / n_sample if n_sample > 0 else 0.0

        # 95% Wilson confidence interval on the hit rate
        from math import sqrt
        z = 1.96
        if n_sample > 0:
            p    = hit_rate
            denom = 1 + z**2 / n_sample
            centre = (p + z**2 / (2 * n_sample)) / denom
            margin = z * sqrt(p * (1 - p) / n_sample + z**2 / (4 * n_sample**2)) / denom
            ci_lo  = max(0.0, centre - margin)
            ci_hi  = min(1.0, centre + margin)
        else:
            ci_lo = ci_hi = 0.0

        estimated_missed   = round(hit_rate * n_non_pass1_seen)
        estimated_philtech = n_confirmed + estimated_missed

        # Recall bounds
        recall_lower = round(ci_lo * n_non_pass1_seen) + n_confirmed
        recall_upper = round(ci_hi * n_non_pass1_seen) + n_confirmed

        # AI cross-reference (use confirmed Pass-1 IDs for the intersection)
        ai_total, ai_ids = ai_data.get(year, (total, set()))
        confirmed_ids = set(
            int(r["job_id"]) for r in confirmed_rows
            if r["is_philtech"] and r["fetch_ok"]
        )
        n_both    = len(confirmed_ids & ai_ids)
        n_pt_only = len(confirmed_ids - ai_ids)
        n_ai_only = len(ai_ids - confirmed_ids)
        # neither uses the recall-adjusted total
        n_neither = max(0, total - (estimated_philtech + n_ai_only))

        print(f"  Pass-1 hits: {n_pass1}  Confirmed: {n_confirmed}  "
              f"Sample: {n_sample_hits}/{n_sample} ({hit_rate:.1%})")
        print(f"  Estimated missed: {estimated_missed}  "
              f"Total estimated: {estimated_philtech}  "
              f"[{recall_lower}, {recall_upper}]")
        print(f"  Phil-tech+AI: {n_both}  PT only: {n_pt_only}  "
              f"AI only: {n_ai_only}  Neither: {n_neither}")

        row = {
            "year":                year,
            "total_jobs":          total,
            "pass1_ids":           n_pass1,
            "pass1_confirmed":     n_confirmed,
            "sample_n":            n_sample,
            "sample_hits":         n_sample_hits,
            "estimated_missed":    estimated_missed,
            "estimated_philtech":  estimated_philtech,
            "ai_jobs":             len(ai_ids),
            "philtech_and_ai":     n_both,
            "philtech_only":       n_pt_only,
            "ai_only":             n_ai_only,
            "neither":             n_neither,
            "recall_lower":        recall_lower,
            "recall_upper":        recall_upper,
        }

        if year not in done_final:
            append_rows(FINAL_CSV, final_fields, [row])
        summary_rows.append(row)

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'Year':>6}  {'Total':>7}  {'P1':>4}  {'Conf':>4}  "
          f"{'Est':>6}  {'Lo':>5}  {'Hi':>5}  "
          f"{'Both':>5}  {'PTonly':>6}  {'AIonly':>6}  {'%PT':>6}  {'%AI':>6}")
    print("-" * 95)
    for r in summary_rows:
        tot = r["total_jobs"] or 1
        print(
            f"{r['year']:>6}  {r['total_jobs']:>7}  "
            f"{r['pass1_ids']:>4}  {r['pass1_confirmed']:>4}  "
            f"{r['estimated_philtech']:>6}  "
            f"{r['recall_lower']:>5}  {r['recall_upper']:>5}  "
            f"{r['philtech_and_ai']:>5}  {r['philtech_only']:>6}  "
            f"{r['ai_only']:>6}  "
            f"{r['estimated_philtech']/tot*100:>5.1f}%  "
            f"{r['ai_jobs']/tot*100:>5.1f}%"
        )
    print(f"\nOutputs written to:\n  {CONFIRMED_CSV}\n  {SAMPLE_CSV}\n  {FINAL_CSV}")


if __name__ == "__main__":
    main()
