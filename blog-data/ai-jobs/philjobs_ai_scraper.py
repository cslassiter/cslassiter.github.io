"""
philjobs_ai_scraper.py
Scrapes PhilJobs.org to count AI-related philosophy job ads by year (2013–present).

Two-pass strategy per year:
  Pass 1 – Paginate ALL jobs and check the visible listing text (title + AOS/AOC)
            for 'AI' as a standalone word or any explicit AI phrase. This captures
            jobs whose AOS is listed as 'AI Ethics', 'Philosophy of AI', etc.

  Pass 2 – Keyword searches for unambiguous multi-word AI phrases; these hit the
            full job description, catching AI mentions buried in the body text.
            Only keywords where EVERY word is ≥3 chars are used (PhilJobs drops
            short tokens like 'AI' and 'of' from keyword queries).

  Union of both pass results = AI job IDs for the year.

Output: philjobs_ai_by_year.csv
"""

import csv
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

OUTPUT = Path(__file__).parent / "philjobs_ai_by_year.csv"
BASE_URL = "https://philjobs.org/jobQuery/execute"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Regex to detect AI mentions in listing text (title + AOS/AOC).
# \bAI\b is case-sensitive; the rest are case-insensitive alternatives.
AI_LISTING_RE = re.compile(
    r"""
    \bAI\b                              # standalone uppercase 'AI'
    | \bartificial\s+intelligence\b     # spelled-out form
    | \bmachine\s+learning\b
    | \bdeep\s+learning\b
    | \bneural\s+network\b
    | \blarge\s+language\s+model\b
    | \blanguage\s+model\b              # catches LLMs without full acronym
    | \bLLM\b                           # acronym (case-sensitive)
    | \bNLP\b                           # acronym (case-sensitive)
    | \bgenerative\s+(?:AI|model)\b
    | \bfoundation\s+model\b
    | \bnatural\s+language\s+processing\b
    | \balgorithmic\s+bias\b
    | \brobotic(?:s)?\b                 # robotics / philosophy of robotics
    | \bAI\s+(?:ethics|safety|governance|alignment|policy|risk)\b
    | \b(?:ethics|governance|safety|policy)\s+of\s+AI\b
    | \bautonomous\s+system\b
    """,
    re.VERBOSE | re.IGNORECASE,
)
# Separate case-sensitive patterns that must NOT be IGNORECASE
AI_LISTING_RE_CS = re.compile(r"\bAI\b|\bLLM\b|\bNLP\b|\bGPT\b")

# Multi-word keyword phrases for PhilJobs description search.
# ALL words must be ≥3 chars (PhilJobs drops shorter tokens as stop words).
# Added: robotics, ethics AI (reverse of original "AI ethics"), language model
AI_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "large language model",
    "language model",               # catches broader LLM references
    "natural language processing",
    "algorithmic bias",
    "machine ethics",
    "computational intelligence",
    "robotics philosophy",          # philosophy of robotics
    "ethics artificial intelligence",  # "ethics of AI" without stop words
    "autonomous systems",
    "foundation model",
    "generative model",
]

YEARS = list(range(2013, 2027))


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_params(year, keyword="", offset=0):
    end_day = 1 if year == 2026 else 31
    end_month = 6 if year == 2026 else 12
    return {
        "jobQuery.fromDate_day":   "1",
        "jobQuery.fromDate_month": "1",
        "jobQuery.fromDate_year":  str(year),
        "jobQuery.toDate_day":     str(end_day),
        "jobQuery.toDate_month":   str(end_month),
        "jobQuery.toDate_year":    str(year),
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
    """Fetch one page; return (total_count, {job_id: listing_text})."""
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

            # Map job_id -> listing block text
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
                # Walk up to find listing block containing AOS info
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
            print(f"    Request error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return 0, {}


# ---------------------------------------------------------------------------
# Pass 1: Scan listing text for AI mentions
# ---------------------------------------------------------------------------

def listing_mentions_ai(text):
    """Return True if listing text (title+AOS) contains an AI-related term."""
    if not text:
        return False
    # Case-sensitive check first (AI, LLM, NLP)
    if AI_LISTING_RE_CS.search(text):
        return True
    # Case-insensitive multi-word phrases
    lc = text.lower()
    for phrase in [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "large language model", "natural language processing",
        "algorithmic bias", "machine ethics", "language model",
        "generative ai", "computational intelligence",
    ]:
        if phrase in lc:
            return True
    return False


def pass1_all_listings(session, year):
    """Paginate through all jobs and return (total, {ai_job_ids})."""
    all_ai_ids = set()
    offset = 0
    total = None

    while True:
        params = make_params(year, keyword="", offset=offset)
        page_total, jobs = fetch_page(session, params)
        time.sleep(0.8)

        if total is None:
            total = page_total

        for job_id, listing_text in jobs.items():
            if listing_mentions_ai(listing_text):
                all_ai_ids.add(job_id)

        if not jobs or (total and offset + 100 >= total):
            break
        offset += 100

    return total or 0, all_ai_ids


# ---------------------------------------------------------------------------
# Pass 2: Keyword searches on full descriptions
# ---------------------------------------------------------------------------

def pass2_keyword_search(session, year):
    """Search each AI keyword phrase; return union of matching job IDs."""
    all_ids = set()
    for kw in AI_KEYWORDS:
        kw_ids = set()
        offset = 0
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    results = []

    for year in YEARS:
        print(f"\n{'='*55}")
        print(f"Year: {year}")

        print("  Pass 1: scanning all listings for AI mentions...")
        total, p1_ids = pass1_all_listings(session, year)
        print(f"  Total jobs: {total}  |  P1 AI jobs: {len(p1_ids)}")

        if total == 0:
            results.append({
                "year": year, "total_jobs": 0, "ai_jobs": 0,
                "proportion": 0.0, "ai_job_ids": "",
            })
            continue

        print("  Pass 2: keyword searches on full descriptions...")
        p2_ids = pass2_keyword_search(session, year)

        all_ai_ids = p1_ids | p2_ids
        ai_count = len(all_ai_ids)
        proportion = ai_count / total if total > 0 else 0.0
        print(f"  P2 keyword AI jobs: {len(p2_ids)}  |  P1+P2 unique: {ai_count}")
        print(f"  => {ai_count} / {total} = {proportion:.1%}")

        results.append({
            "year": year,
            "total_jobs": total,
            "ai_jobs": ai_count,
            "proportion": round(proportion, 6),
            "ai_job_ids": "|".join(str(i) for i in sorted(all_ai_ids)),
        })

    # Write CSV
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["year", "total_jobs", "ai_jobs", "proportion", "ai_job_ids"],
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults written to {OUTPUT}")

    # Summary table
    print(f"\n{'Year':>6}  {'Total':>7}  {'AI Jobs':>8}  {'%':>7}")
    print("-" * 35)
    for row in results:
        print(
            f"{row['year']:>6}  {row['total_jobs']:>7}  "
            f"{row['ai_jobs']:>8}  {row['proportion']*100:>6.1f}%"
        )


if __name__ == "__main__":
    main()
