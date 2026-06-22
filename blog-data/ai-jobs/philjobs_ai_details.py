"""
philjobs_ai_details.py
Fetch individual job pages for all AI-flagged PhilJobs ads and extract
institution name, job category, and contract type.

Reads:  philjobs_ai_by_year.csv (job IDs)
Writes: philjobs_ai_jobs_detail.csv
"""

import csv
import re
import time
import requests
from bs4 import BeautifulSoup
from collections import Counter
from pathlib import Path

IN_CSV  = Path(__file__).parent / "philjobs_ai_by_year.csv"
OUT_CSV = Path(__file__).parent / "philjobs_ai_jobs_detail.csv"
BASE    = "https://philjobs.org/job/show/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def fetch_job(session, job_id, retries=3):
    url = f"{BASE}{job_id}"
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except requests.RequestException as e:
            print(f"  Error job {job_id} attempt {attempt+1}: {e}")
            if attempt < retries - 1:
                time.sleep(4)
    return None


def extract_fields(soup, job_id):
    """Pull institution, job category, contract type from a job page.

    PhilJobs structure:
      <h1>  Job title
      <h2>  Department, Institution
      <table class="details">
        <tr class="prop">
          <td class="name">Field label</td>
          <td class="value">Value</td>
        </tr> ...
    """
    # Job title from h1
    h1 = soup.find("h1")
    job_title = clean(h1.get_text()) if h1 else ""

    # Institution (and department) from h2
    h2 = soup.find("h2")
    raw_h2 = clean(h2.get_text()) if h2 else ""
    # h2 may be "Department, University" — take the last comma-separated part as institution
    if "," in raw_h2:
        parts = [p.strip() for p in raw_h2.split(",")]
        institution = parts[-1]
        department  = ", ".join(parts[:-1])
    else:
        institution = raw_h2
        department  = ""

    # Structured fields from the details table
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
        "job_title":    job_title,
        "institution":  institution,
        "department":   department,
        "job_category": job_category,
        "aos":          aos,
        "location":     location,
    }


# Standardise job category into 5 buckets
_CAT_RE = [
    (r"grad(uate)?\s*student|phd\s*fellow|dissertation",       "Graduate fellowship"),
    (r"postdoc|post.doctoral|post doctoral|post.doc",           "Postdoc or similar"),
    (r"visiting|sabbatical",                                    "Visiting/Temp"),
    (r"junior\s*faculty|assistant\s*prof|instructor|lecturer",  "Junior faculty"),
    (r"senior\s*faculty|associate\s*prof|full\s*prof|endowed|chaired|tenured",
                                                                "Senior faculty"),
    (r"tenure.track|tenure\s*eligible|tenure\s*stream",        "Tenure-track"),
    (r"admin|director|dean",                                    "Admin"),
]
_CAT_COMPILED = [(re.compile(p, re.I), label) for p, label in _CAT_RE]

def std_category(raw):
    for pat, label in _CAT_COMPILED:
        if pat.search(raw or ""):
            return label
    return "Other/Open"


def main():
    # Collect all unique AI job IDs with their year
    id_to_year = {}
    with open(IN_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yr = int(row["year"])
            for jid in (row["ai_job_ids"] or "").split("|"):
                if jid.strip():
                    id_to_year[int(jid)] = yr

    job_ids = sorted(id_to_year.keys())
    print(f"Fetching {len(job_ids)} AI job pages...")

    session = requests.Session()
    session.headers.update(HEADERS)

    detail_rows = []
    for i, job_id in enumerate(job_ids, 1):
        if i % 50 == 0:
            print(f"  {i}/{len(job_ids)}...")
        soup = fetch_job(session, job_id)
        if soup is None:
            detail_rows.append({
                "job_id": job_id, "year": id_to_year[job_id],
                "job_title": "", "institution": "", "department": "",
                "job_category": "", "std_category": "Unknown", "aos": "", "location": "",
            })
            continue

        fields = extract_fields(soup, job_id)
        cat_raw = fields["job_category"]
        fields["year"] = id_to_year[job_id]
        fields["std_category"] = std_category(cat_raw)
        detail_rows.append(fields)
        time.sleep(0.6)

    # Write detail CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["job_id","year","institution","department","job_title",
                        "job_category","std_category","aos","location"],
        )
        writer.writeheader()
        writer.writerows(detail_rows)
    print(f"\nDetail CSV written: {OUT_CSV}")

    # ---- Top 10 institutions ----
    inst_counter = Counter()
    for row in detail_rows:
        inst = row["institution"].strip()
        if inst:
            inst_counter[inst] += 1

    print("\nTop 10 institutions posting AI philosophy jobs (2013-2026):")
    print(f"{'Rank':>4}  {'Institution':<55}  {'Ads':>4}")
    print("-" * 70)
    for rank, (inst, cnt) in enumerate(inst_counter.most_common(20), 1):
        print(f"{rank:>4}  {inst:<55}  {cnt:>4}")
        if rank >= 20:
            break

    # ---- Job type breakdown ----
    cat_counter = Counter(r["std_category"] for r in detail_rows)
    total = len(detail_rows)
    print(f"\nJob type breakdown (total AI ads = {total}):")
    print(f"{'Category':<25}  {'Count':>5}  {'%':>6}")
    print("-" * 40)
    for cat, cnt in cat_counter.most_common():
        print(f"{cat:<25}  {cnt:>5}  {cnt/total*100:>5.1f}%")

    # ---- Job type by year ----
    from collections import defaultdict
    year_cat = defaultdict(Counter)
    for row in detail_rows:
        year_cat[row["year"]][row["std_category"]] += 1

    print("\nJob type by year:")
    cats = ["Tenure-track","Junior faculty","Senior faculty","Postdoc or similar",
            "Visiting/Temp","Graduate fellowship","Other/Open"]
    header = f"{'Year':>6}" + "".join(f"  {c[:10]:>10}" for c in cats)
    print(header)
    print("-" * (len(header) + 5))
    for yr in sorted(year_cat.keys()):
        row_str = f"{yr:>6}"
        for c in cats:
            row_str += f"  {year_cat[yr].get(c, 0):>10}"
        print(row_str)


if __name__ == "__main__":
    main()
