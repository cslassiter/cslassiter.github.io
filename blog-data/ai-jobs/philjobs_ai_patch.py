"""
philjobs_ai_patch.py

Two-part patch to the AI jobs dataset:

Part A  Verify the 3 Minerva Schools at KGI job pages for AI content.
        Remove any that have no AI content (same procedure as Wake Forest).

Part B  Fetch full details for the 14 genuinely missed AI jobs found by
        the false-negative audit and add them to the dataset.

Updates:
  philjobs_ai_jobs_detail.csv   add new rows, remove false positives
  philjobs_ai_by_year.csv       update ai_jobs counts and ai_job_ids
"""

import csv, re, time, requests
from bs4 import BeautifulSoup
from pathlib import Path
from collections import defaultdict

BASE_DIR    = Path(__file__).parent
DETAIL_CSV  = BASE_DIR / "philjobs_ai_jobs_detail.csv"
YEAR_CSV    = BASE_DIR / "philjobs_ai_by_year.csv"
JOB_URL     = "https://philjobs.org/job/show/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Same broad regex as the audit
AI_VERIFY_RE = re.compile(
    r"""
    \bartificial\s+intelligence\b
    | \bmachine\s+learning\b
    | \bdeep\s+learning\b
    | \bneural\s+network\b
    | \blarge\s+language\s+model\b
    | \blanguage\s+model\b
    | \bgenerative\s+(?:AI|model)\b
    | \bfoundation\s+model\b
    | \bnatural\s+language\s+processing\b
    | \balgorithmic\s+bias\b
    | \bmachine\s+ethics\b
    | \bcomputational\s+intelligence\b
    | \bAI\s+(?:ethics|safety|governance|alignment|policy|regulation|bias|risk)\b
    | \b(?:ethics|governance|safety|policy)\s+of\s+AI\b
    | \brobotic(?:s)?\b
    | \bautonomous\s+system\b
    | \btransformer\s+model\b
    | \bChatGPT\b
    | \bGPT[-\s]?\d
    | \bRLHF\b
    | \bAI\s+alignment\b
    """,
    re.VERBOSE | re.IGNORECASE,
)
AI_VERIFY_CS = re.compile(r"\bAI\b|\bLLM\b|\bNLP\b|\bGPT\b")

def mentions_ai(text):
    if not text:
        return False
    return bool(AI_VERIFY_RE.search(text) or AI_VERIFY_CS.search(text))


def fetch_soup(session, job_id, retries=3):
    url = f"{JOB_URL}{job_id}"
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except requests.RequestException as e:
            print(f"    Job {job_id} error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(4)
    return None


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def extract_fields(soup, job_id, year):
    h1 = soup.find("h1")
    job_title = clean(h1.get_text()) if h1 else ""

    h2 = soup.find("h2")
    raw_h2 = clean(h2.get_text()) if h2 else ""
    if "," in raw_h2:
        parts = [p.strip() for p in raw_h2.split(",")]
        institution = parts[-1]
        department  = ", ".join(parts[:-1])
    else:
        institution = raw_h2
        department  = ""

    fields = {}
    for tr in soup.find_all("tr", class_="prop"):
        name_td  = tr.find("td", class_="name")
        value_td = tr.find("td", class_="value")
        if name_td and value_td:
            key = clean(name_td.get_text()).lower().rstrip(":")
            val = clean(value_td.get_text())
            fields[key] = val

    job_category = fields.get("job category", "")
    aos          = fields.get("aos", "")
    location     = fields.get("location", "")

    return {
        "job_id":       job_id,
        "year":         year,
        "institution":  institution,
        "department":   department,
        "job_title":    job_title,
        "job_category": job_category,
        "std_category": std_category(job_category),
        "aos":          aos,
        "location":     location,
    }


_CAT_RE = [
    (r"grad(uate)?\s*student|phd\s*fellow|dissertation",       "Graduate fellowship"),
    (r"postdoc|post.doctoral|post doctoral|post.doc",          "Postdoc or similar"),
    (r"visiting|sabbatical",                                   "Visiting/Temp"),
    (r"junior\s*faculty|assistant\s*prof|instructor|lecturer", "Junior faculty"),
    (r"senior\s*faculty|associate\s*prof|full\s*prof|endowed|chaired|tenured",
                                                               "Senior faculty"),
    (r"tenure.track|tenure\s*eligible|tenure\s*stream",       "Tenure-track"),
    (r"admin|director|dean",                                   "Admin"),
]
_CAT_COMPILED = [(re.compile(p, re.I), label) for p, label in _CAT_RE]

def std_category(raw):
    for pat, label in _CAT_COMPILED:
        if pat.search(raw or ""):
            return label
    return "Other/Open"


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    # Load current detail rows
    detail_rows = []
    fieldnames  = None
    with open(DETAIL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        detail_rows = list(reader)

    existing_ids = {int(r["job_id"]) for r in detail_rows}

    # ── Part A: Verify Minerva Schools jobs ──────────────────────────────────

    print("\n" + "="*60)
    print("PART A: Minerva Schools verification")
    print("="*60)

    minerva_ids = [int(r["job_id"]) for r in detail_rows
                   if "minerva" in r["institution"].lower()]
    print(f"Minerva jobs in dataset: {len(minerva_ids)} — {minerva_ids}")

    minerva_remove = []
    for jid in minerva_ids:
        soup = fetch_soup(session, jid)
        text = soup.get_text(separator=" ", strip=True) if soup else ""
        is_ai = mentions_ai(text)
        status = "CONFIRMED" if is_ai else "NO AI FOUND — removing"
        print(f"  Job {jid}: {status}")
        if not is_ai:
            minerva_remove.append(jid)
        time.sleep(0.6)

    if minerva_remove:
        before = len(detail_rows)
        detail_rows = [r for r in detail_rows if int(r["job_id"]) not in minerva_remove]
        print(f"\nRemoved {before - len(detail_rows)} Minerva false positives: {minerva_remove}")
    else:
        print("\nAll Minerva jobs confirmed — no removals.")

    # ── Part B: Fetch and add the 14 missed jobs ─────────────────────────────

    print("\n" + "="*60)
    print("PART B: Adding missed jobs from FN audit")
    print("="*60)

    missed = [
        (13174, 2019), (15462, 2020), (15470, 2020),
        (25241, 2023), (26850, 2024), (30194, 2025),
        (30461, 2025), (30477, 2025), (30530, 2025),
        (31029, 2026), (31221, 2026), (31393, 2026),
        (31513, 2026), (31517, 2026),
    ]

    new_rows = []
    for jid, yr in missed:
        if jid in existing_ids:
            print(f"  Job {jid}: already in dataset, skipping")
            continue
        soup = fetch_soup(session, jid)
        if soup is None:
            print(f"  Job {jid}: fetch failed, skipping")
            continue
        text = soup.get_text(separator=" ", strip=True)
        if not mentions_ai(text):
            print(f"  Job {jid}: AI no longer found on page — skipping")
            continue
        row = extract_fields(soup, jid, yr)
        new_rows.append(row)
        print(f"  Job {jid} ({yr}): added — {row['institution']} | "
              f"{row['job_title'][:55]}")
        time.sleep(0.6)

    detail_rows.extend(new_rows)
    detail_rows.sort(key=lambda r: (int(r["year"]), int(r["job_id"])))

    # ── Write corrected detail CSV ────────────────────────────────────────────

    with open(DETAIL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(detail_rows)
    print(f"\nDetail CSV updated: {len(detail_rows)} rows")

    # ── Update philjobs_ai_by_year.csv ────────────────────────────────────────

    print("\nUpdating year CSV...")
    year_rows = []
    with open(YEAR_CSV, newline="", encoding="utf-8") as f:
        year_rows = list(csv.DictReader(f))

    # Rebuild ai_job_ids and counts from corrected detail CSV
    ids_by_year = defaultdict(set)
    for r in detail_rows:
        ids_by_year[int(r["year"])].add(int(r["job_id"]))

    for yr in year_rows:
        y = int(yr["year"])
        new_ids = ids_by_year.get(y, set())
        yr["ai_jobs"]     = len(new_ids)
        yr["proportion"]  = round(len(new_ids) / int(yr["total_jobs"]), 6) if int(yr["total_jobs"]) else 0
        yr["ai_job_ids"]  = "|".join(str(i) for i in sorted(new_ids))

    with open(YEAR_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year","total_jobs","ai_jobs","proportion","ai_job_ids"])
        w.writeheader()
        w.writerows(year_rows)

    # ── Summary ───────────────────────────────────────────────────────────────

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"  Minerva false positives removed: {len(minerva_remove)}")
    print(f"  Missed jobs added:               {len(new_rows)}")
    net = len(new_rows) - len(minerva_remove)
    print(f"  Net change in dataset size:      {net:+d}")
    print(f"  Final dataset size:              {len(detail_rows)} jobs")
    print()
    print("Year-by-year totals after patch:")
    print(f"  {'Year':>6}  {'Total ads':>9}  {'AI jobs':>7}  {'%':>6}")
    print("  " + "-"*32)
    for yr in year_rows:
        pct = float(yr["proportion"]) * 100
        print(f"  {yr['year']:>6}  {yr['total_jobs']:>9}  {yr['ai_jobs']:>7}  {pct:>5.1f}%")


if __name__ == "__main__":
    main()
