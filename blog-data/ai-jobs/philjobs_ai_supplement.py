"""
philjobs_ai_supplement.py

Targeted supplementary scrape using only the NEW keywords added to the
AI scraper (terms not in the original list). Finds any jobs missed by
the original scrape and adds them to the dataset.

New keywords: language model, robotics philosophy, ethics artificial
intelligence, autonomous systems, foundation model, generative model.

Does NOT overwrite existing corrections — only adds genuinely new jobs.
"""

import csv, re, time, requests
from bs4 import BeautifulSoup
from pathlib import Path
from collections import defaultdict

BASE_DIR   = Path(__file__).parent
DETAIL_CSV = BASE_DIR / "philjobs_ai_jobs_detail.csv"
YEAR_CSV   = BASE_DIR / "philjobs_ai_by_year.csv"
BASE_URL   = "https://philjobs.org/jobQuery/execute"
JOB_URL    = "https://philjobs.org/job/show/"
YEARS      = list(range(2013, 2027))

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

NEW_KEYWORDS = [
    "language model",
    "robotics philosophy",
    "ethics artificial intelligence",
    "autonomous systems",
    "foundation model",
    "generative model",
]

AI_VERIFY_RE = re.compile(
    r"\bartificial\s+intelligence\b|\bmachine\s+learning\b|\bdeep\s+learning\b"
    r"|\bneural\s+network\b|\blanguage\s+model\b|\bfoundation\s+model\b"
    r"|\bnatural\s+language\s+processing\b|\balgorithmic\s+bias\b"
    r"|\bmachine\s+ethics\b|\bcomputational\s+intelligence\b"
    r"|\bAI\s+(?:ethics|safety|governance|alignment|policy|risk)\b"
    r"|\b(?:ethics|governance|safety|policy)\s+of\s+AI\b"
    r"|\brobotic(?:s)?\b|\bautonomous\s+system\b|\bgenerative\s+(?:AI|model)\b",
    re.IGNORECASE,
)
AI_CS = re.compile(r"\bAI\b|\bLLM\b|\bNLP\b|\bGPT\b")

def mentions_ai(text):
    return bool(text and (AI_VERIFY_RE.search(text) or AI_CS.search(text)))

def make_params(year, keyword, offset=0):
    end_month = 6 if year == 2026 else 12
    return {
        "jobQuery.fromDate_day": "1", "jobQuery.fromDate_month": "1",
        "jobQuery.fromDate_year": str(year), "jobQuery.toDate_day": "31",
        "jobQuery.toDate_month": str(end_month), "jobQuery.toDate_year": str(year),
        "withExpired": "true", "format": "", "create": "Search",
        "jobQuery.orderBy": "DATE", "withStubs": "true",
        "withExcluded": "true", "withSaved": "true",
        "jobQuery.keywords": keyword, "offset": str(offset), "max": "100",
    }

def fetch_listing_page(session, params, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(BASE_URL, params=params, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            total = 0
            for el in soup.find_all(True):
                m = re.search(r"found\s+([\d,]+)\s+ads", el.get_text(strip=True), re.I)
                if m:
                    total = int(m.group(1).replace(",", "")); break
            ids = set()
            for a in soup.find_all("a", href=True):
                m = re.match(r"/job/show/(\d+)$", a["href"])
                if m: ids.add(int(m.group(1)))
            return total, ids
        except requests.RequestException as e:
            if attempt < retries - 1: time.sleep(5)
    return 0, set()

def fetch_soup(session, job_id, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(f"{JOB_URL}{job_id}", timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except requests.RequestException:
            if attempt < retries - 1: time.sleep(4)
    return None

def clean(s): return re.sub(r"\s+", " ", s or "").strip()

_CAT = [(re.compile(p, re.I), l) for p, l in [
    (r"grad(uate)?\s*student|phd\s*fellow|dissertation", "Graduate fellowship"),
    (r"postdoc|post.doctoral|post.doc", "Postdoc or similar"),
    (r"visiting|sabbatical", "Visiting/Temp"),
    (r"junior\s*faculty|assistant\s*prof|instructor|lecturer", "Junior faculty"),
    (r"senior\s*faculty|associate\s*prof|full\s*prof|endowed|chaired|tenured", "Senior faculty"),
    (r"tenure.track|tenure\s*eligible", "Tenure-track"),
    (r"admin|director|dean", "Admin"),
]]
def std_cat(raw):
    for pat, label in _CAT:
        if pat.search(raw or ""): return label
    return "Other/Open"

def extract_fields(soup, jid, yr):
    h1 = soup.find("h1"); title = clean(h1.get_text()) if h1 else ""
    h2 = soup.find("h2"); raw_h2 = clean(h2.get_text()) if h2 else ""
    if "," in raw_h2:
        parts = [p.strip() for p in raw_h2.split(",")]
        inst, dept = parts[-1], ", ".join(parts[:-1])
    else:
        inst, dept = raw_h2, ""
    fields = {}
    for tr in soup.find_all("tr", class_="prop"):
        n = tr.find("td", class_="name"); v = tr.find("td", class_="value")
        if n and v: fields[clean(n.get_text()).lower().rstrip(":")] = clean(v.get_text())
    jcat = fields.get("job category", "")
    return {"job_id": jid, "year": yr, "institution": inst, "department": dept,
            "job_title": title, "job_category": jcat, "std_category": std_cat(jcat),
            "aos": fields.get("aos", ""), "location": fields.get("location", "")}

def main():
    # Load existing job IDs
    existing_ids = set()
    detail_rows = []
    fieldnames = None
    with open(DETAIL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        detail_rows = list(reader)
        existing_ids = {int(r["job_id"]) for r in detail_rows}

    print(f"Existing dataset: {len(existing_ids)} jobs")
    session = requests.Session(); session.headers.update(HEADERS)

    candidate_ids = defaultdict(set)  # year -> new job IDs

    for year in YEARS:
        print(f"\nYear {year}:")
        for kw in NEW_KEYWORDS:
            offset, kw_total = 0, None
            while True:
                total, ids = fetch_listing_page(session, make_params(year, kw, offset))
                time.sleep(0.7)
                if kw_total is None: kw_total = total
                new = ids - existing_ids
                if new: candidate_ids[year] |= new
                if not ids or (kw_total and offset + 100 >= kw_total): break
                offset += 100
        if candidate_ids[year]:
            print(f"  {len(candidate_ids[year])} candidate new jobs")

    # Fetch and verify candidates
    new_rows = []
    all_candidates = [(yr, jid) for yr, ids in candidate_ids.items() for jid in ids]
    print(f"\nFetching {len(all_candidates)} candidate pages for verification...")

    for i, (yr, jid) in enumerate(sorted(all_candidates), 1):
        if i % 25 == 0: print(f"  {i}/{len(all_candidates)}...")
        soup = fetch_soup(session, jid)
        if soup is None: continue
        text = soup.get_text(separator=" ", strip=True)
        if not mentions_ai(text): continue
        row = extract_fields(soup, jid, yr)
        new_rows.append(row)
        print(f"  + Job {jid} ({yr}): {row['institution']} | {row['job_title'][:55]}")
        time.sleep(0.6)

    if not new_rows:
        print("\nNo new confirmed AI jobs found.")
        return

    # Update detail CSV
    detail_rows.extend(new_rows)
    detail_rows.sort(key=lambda r: (int(r["year"]), int(r["job_id"])))
    with open(DETAIL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(detail_rows)

    # Update year CSV
    ids_by_year = defaultdict(set)
    for r in detail_rows: ids_by_year[int(r["year"])].add(int(r["job_id"]))
    year_rows = list(csv.DictReader(open(YEAR_CSV, newline="", encoding="utf-8")))
    for yr in year_rows:
        y = int(yr["year"]); new_ids = ids_by_year.get(y, set())
        yr["ai_jobs"] = len(new_ids)
        yr["proportion"] = round(len(new_ids)/int(yr["total_jobs"]), 6)
        yr["ai_job_ids"] = "|".join(str(i) for i in sorted(new_ids))
    with open(YEAR_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year","total_jobs","ai_jobs","proportion","ai_job_ids"])
        w.writeheader(); w.writerows(year_rows)

    print(f"\nAdded {len(new_rows)} new jobs. Final dataset: {len(detail_rows)}")

if __name__ == "__main__":
    main()
