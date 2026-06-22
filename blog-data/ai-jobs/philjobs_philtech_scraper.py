"""
philjobs_philtech_scraper.py

Scrapes PhilJobs.org for philosophy-of-technology and STS job ads (2013–present).
Cross-references with existing AI job IDs (philjobs_ai_by_year.csv) to produce
four groups per year:

  phil_tech_only    – phil-tech / STS mention, no AI mention
  phil_tech_and_ai  – both phil-tech / STS and AI mentioned
  ai_only           – AI mention, no phil-tech / STS
  neither           – neither

Two-pass strategy (mirrors philjobs_ai_scraper.py):
  Pass 1 – Paginate ALL jobs for the year; scan listing text (title + AOS/AOC)
            with a regex covering phil-tech and STS phrases.
  Pass 2 – PhilJobs keyword searches on full descriptions.
            Note: PhilJobs drops tokens shorter than 3 chars ("of", "and"),
            so "philosophy of technology" becomes the query "philosophy technology".

Output: philjobs_philtech_by_year.csv
"""

import csv
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

AI_CSV  = Path(__file__).parent / "philjobs_ai_by_year.csv"
OUT_CSV = Path(__file__).parent / "philjobs_philtech_by_year.csv"
BASE_URL = "https://philjobs.org/jobQuery/execute"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

YEARS = list(range(2013, 2027))


# ── Pass 1: regex for listing text (title + AOS/AOC) ─────────────────────────

PHILTECH_RE = re.compile(
    r"""
    philosophy\s+of\s+technolog         # philosophy of technology/technological
    | post[- ]?phenomenolog             # post-phenomenology / postphenomenology
    | \bSTS\b                           # Science and Technology Studies acronym
    | science\s+and\s+technology\s+stud # science and technology studies
    | technology\s+studies              # technology studies (standalone)
    | philosophy\s+of\s+media           # philosophy of media
    | philosophy\s+of\s+engineering     # philosophy of engineering
    | critical\s+technolog              # critical technology / technologies
    | empirical\s+turn                  # the empirical turn (classic phil-tech phrase)
    | \bphil\w*\s+of\s+tech\b          # abbreviated forms (phil. of tech)
    | ethics\s+of\s+technolog           # ethics of technology (common European phrasing)
    | \bdigital\s+ethics\b              # digital ethics (post-2018 growth field)
    | philosophy\s+of\s+computing       # philosophy of computing
    | sociotechnical                    # sociotechnical (STS core term)
    | technoscience                     # technoscience (STS term)
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ── Pass 2: keyword phrases for PhilJobs full-text search ────────────────────
# PhilJobs does token AND-matching, NOT exact phrase matching. This means:
#   - "of" and "and" (< 3 chars) are dropped as stop words
#   - Short tokens like "STS" match as substrings (e.g. "STS" hits "interests",
#     "exists", "suggests") → catastrophic false-positive rate; excluded
#   - "post-phenomenology" splits on hyphen → "post" matches "postdoc"/"posting"
#     in nearly every ad → excluded
# Only include phrases where every token is specific enough to avoid false positives
# when AND-matched across the full document.

PHILTECH_KEYWORDS = [
    "technology studies",           # specific standalone phrase
    "science technology studies",   # "science and technology studies" (drops "and")
    "critical technologies",        # reasonably specific to phil-tech discourse
    "empirical turn",               # classic phrase in phil-tech tradition
    "philosophy technology ethics", # three-way AND; catches ethics-of-tech ads
    "sociotechnical",               # single distinctive STS token
    "technoscience",                # single distinctive STS token
    "digital ethics",               # two distinctive AND-matched tokens
    "philosophy computing",         # philosophy of computing (drops "of")
    "ethics technology",            # ethics of technology (drops "of")
]


# ── HTTP helpers (identical to philjobs_ai_scraper.py) ───────────────────────

def make_params(year, keyword="", offset=0):
    end_day   = 31 if year < 2026 else 31
    end_month = 12 if year < 2026 else 5
    end_year  = year
    return {
        "jobQuery.fromDate_day":   "1",
        "jobQuery.fromDate_month": "1",
        "jobQuery.fromDate_year":  str(year),
        "jobQuery.toDate_day":     str(end_day),
        "jobQuery.toDate_month":   str(end_month),
        "jobQuery.toDate_year":    str(end_year),
        "withExpired":             "true",
        "format":                  "",
        "create":                  "Search",
        "jobQuery.orderBy":        "DATE",
        "withStubs":               "true",
        "withExcluded":            "true",
        "withSaved":               "true",
        "jobQuery.keywords":       keyword,
        "offset":                  str(offset),
        "max":                     "100",
    }


def fetch_page(session, params, retries=3):
    """Fetch one results page; return (total_count, {job_id: listing_text})."""
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
            print(f"    Request error (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return 0, {}


# ── Pass 1: scan all listing texts ───────────────────────────────────────────

def pass1_all_listings(session, year):
    """Paginate all jobs; return (total_ads, set of phil-tech job IDs)."""
    philtech_ids = set()
    offset = 0
    total  = None

    while True:
        params = make_params(year, keyword="", offset=offset)
        page_total, jobs = fetch_page(session, params)
        time.sleep(0.8)

        if total is None:
            total = page_total

        for job_id, listing_text in jobs.items():
            if PHILTECH_RE.search(listing_text):
                philtech_ids.add(job_id)

        if not jobs or (total and offset + 100 >= total):
            break
        offset += 100

    return total or 0, philtech_ids


# ── Pass 2: keyword searches on full descriptions ────────────────────────────

def pass2_keyword_search(session, year):
    """Search each phil-tech keyword phrase; return union of matching job IDs."""
    all_ids = set()
    for kw in PHILTECH_KEYWORDS:
        kw_ids  = set()
        offset  = 0
        kw_total = None

        while True:
            params = make_params(year, keyword=kw, offset=offset)
            page_total, jobs = fetch_page(session, params)
            time.sleep(0.7)

            if kw_total is None:
                kw_total = page_total

            kw_ids |= set(jobs.keys())

            if not jobs or (kw_total and offset + 100 >= kw_total):
                break
            offset += 100

        if kw_ids:
            print(f"    '{kw}': {len(kw_ids)} jobs")
        all_ids |= kw_ids

    return all_ids


# ── Load existing AI job IDs ──────────────────────────────────────────────────

def load_ai_ids():
    """Return {year: (total_jobs, set_of_ai_job_ids)} from the AI CSV."""
    ai_data = {}
    if not AI_CSV.exists():
        print(f"WARNING: {AI_CSV} not found — AI cross-reference will be empty.")
        return ai_data
    with open(AI_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            year = int(row["year"])
            total = int(row["total_jobs"])
            ids = set()
            for jid in (row.get("ai_job_ids") or "").split("|"):
                if jid.strip():
                    ids.add(int(jid))
            ai_data[year] = (total, ids)
    return ai_data


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ai_data = load_ai_ids()
    session = requests.Session()
    session.headers.update(HEADERS)

    results = []

    for year in YEARS:
        print(f"\n{'=' * 60}")
        print(f"Year: {year}")

        print("  Pass 1: scanning all listings for phil-tech / STS mentions...")
        total_scraped, p1_ids = pass1_all_listings(session, year)
        print(f"  Total ads: {total_scraped}  |  P1 phil-tech: {len(p1_ids)}")

        # Use AI CSV total if available (it's already been validated)
        total_ai, ai_ids = ai_data.get(year, (total_scraped, set()))
        total = total_ai if total_ai else total_scraped

        if total == 0:
            results.append({
                "year": year, "total_jobs": 0,
                "philtech_jobs": 0, "ai_jobs": 0,
                "philtech_and_ai": 0, "philtech_only": 0,
                "ai_only": 0, "neither": 0,
                "pct_philtech": 0.0, "pct_ai": 0.0, "pct_philtech_and_ai": 0.0,
                "philtech_job_ids": "",
            })
            continue

        print("  Pass 2: keyword searches on full descriptions...")
        p2_ids = pass2_keyword_search(session, year)

        philtech_ids = p1_ids | p2_ids
        n_pt   = len(philtech_ids)
        n_ai   = len(ai_ids)
        n_both = len(philtech_ids & ai_ids)
        n_pt_only = len(philtech_ids - ai_ids)
        n_ai_only = len(ai_ids - philtech_ids)
        n_neither = total - len(philtech_ids | ai_ids)

        print(f"  Phil-tech (P1+P2): {n_pt}  |  AI: {n_ai}  |  Both: {n_both}")
        print(f"  phil_tech_only={n_pt_only}  ai_only={n_ai_only}  "
              f"neither={n_neither}  total={total}")

        results.append({
            "year":              year,
            "total_jobs":        total,
            "philtech_jobs":     n_pt,
            "ai_jobs":           n_ai,
            "philtech_and_ai":   n_both,
            "philtech_only":     n_pt_only,
            "ai_only":           n_ai_only,
            "neither":           n_neither,
            "pct_philtech":      round(n_pt   / total, 6),
            "pct_ai":            round(n_ai   / total, 6),
            "pct_philtech_and_ai": round(n_both / total, 6),
            "philtech_job_ids":  "|".join(str(i) for i in sorted(philtech_ids)),
        })

    # Write CSV
    fieldnames = [
        "year", "total_jobs", "philtech_jobs", "ai_jobs",
        "philtech_and_ai", "philtech_only", "ai_only", "neither",
        "pct_philtech", "pct_ai", "pct_philtech_and_ai", "philtech_job_ids",
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults written to {OUT_CSV}")

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'Year':>6}  {'Total':>7}  {'PhilTech':>9}  {'AI':>6}  "
          f"{'Both':>6}  {'PT only':>8}  {'AI only':>8}  "
          f"{'%PT':>6}  {'%AI':>6}  {'%Both':>6}")
    print("-" * 80)
    for row in results:
        print(
            f"{row['year']:>6}  {row['total_jobs']:>7}  "
            f"{row['philtech_jobs']:>9}  {row['ai_jobs']:>6}  "
            f"{row['philtech_and_ai']:>6}  {row['philtech_only']:>8}  "
            f"{row['ai_only']:>8}  "
            f"{row['pct_philtech']*100:>5.1f}%  "
            f"{row['pct_ai']*100:>5.1f}%  "
            f"{row['pct_philtech_and_ai']*100:>5.1f}%"
        )


if __name__ == "__main__":
    main()
