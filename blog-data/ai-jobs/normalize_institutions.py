"""
normalize_institutions.py

Cleans institution names in philjobs_ai_jobs_detail.csv:
  1. Strips encoding artifacts and trailing junk
  2. Removes "not BA-granting" suffixes
  3. Removes leading "the " / "The "
  4. Merges clear name variants for the same institution
  5. Re-fetches ambiguous partial names (city-only entries) from PhilJobs
     to recover the correct institution
"""

import csv, re, time, requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE_DIR   = Path(__file__).parent
DETAIL_CSV = BASE_DIR / "philjobs_ai_jobs_detail.csv"
JOB_URL    = "https://philjobs.org/job/show/"
HEADERS    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── Step 1: deterministic string-level rules ──────────────────────────────────
# Applied in order; first match wins where names are exact.

REPLACEMENTS = {
    # Encoding artifacts → clean names
    "Umeé University":                          "Umea University",
    "Ume� University":                          "Umea University",
    "Universit� Erlangen-N� rnberg":       "Friedrich-Alexander-University Erlangen-Nuremberg",
    "Universität Erlangen-Nürnberg":       "Friedrich-Alexander-University Erlangen-Nuremberg",
    "Universit� t Bonn":                        "University of Bonn",
    "Universität Bonn":                         "University of Bonn",
    "Rheinische Friedrich-Wilhelms-Universit� t Bonn": "University of Bonn",
    "Universität Hamburg":                      "Universitat Hamburg",
    "Universit� t Hamburg":                     "Universitat Hamburg",
    "Universit� des Saarlandes":                "Universitat des Saarlandes",
    "Université du Québec à Trois-Rivières": "Université du Québec à Trois-Rivières",
    "Université degli Studi dell'Aquila":       "Università degli Studi dell'Aquila",
    "Université Autónoma de Barcelona":    "Universitat Autònoma de Barcelona",
    "Universitat Aut� noma de Barcelona":       "Universitat Autònoma de Barcelona",
    "Centre de recherche en � thique (CR� )": "Centre de recherche en éthique (CRÉ)",
    "UNIVERSITE DE MONTREAL":                        "University of Montreal",
    "Florida Atlantic University - FAU �":       "Florida Atlantic University",
    "Florida Atlantic University �":             "Florida Atlantic University",
    "Florida Atlantic University - FAU":              "Florida Atlantic University",

    # "the X" → "X"
    "the University of Hong Kong":                   "University of Hong Kong",
    "the University of Western Australia":           "University of Western Australia",

    # Clear name variants → canonical form
    "Technical University of Eindhoven":             "Eindhoven University of Technology",
    "Universiteit Utrecht":                          "Utrecht University",
    "Oxford":                                        "University of Oxford",
    "University of Oxford in association with Corpus Christi College": "University of Oxford",
    "Cambridge University":                          "University of Cambridge",
    "Ruhr-University Bochum":                        "Ruhr University Bochum",
    "Ruhr-Universität Bochum":                 "Ruhr University Bochum",
    "Stanford University McCoy Family Center for Ethics in Society & the Institute for Human-Centered AI": "Stanford University",
    "Harvard School of Public Health":               "Harvard University",
    "London School of Economics and Political Science": "London School of Economics",
    "SUNY Geneseo":                                  "SUNY Geneseo",
    "State University of New York at Geneseo":       "SUNY Geneseo",
    "NYU Tandon School of Engineering not BA-granting": "NYU Tandon School of Engineering",
    "Carnegie Mellon University not BA-granting":    "Carnegie Mellon University",
    "University of Electronic Science and Technology of China not BA-granting": "University of Electronic Science and Technology of China",
    "University of Cambridge and University of Bonn": "University of Cambridge",  # dual listing; assign primary
    "Aarhus University":                             "University of Aarhus",
}

# Regex-level cleanups applied after the mapping
def clean_name(name):
    name = name.strip()
    # Strip "not BA-granting" suffix (various spacings)
    name = re.sub(r"\s+not\s+BA[-\s]granting.*$", "", name, flags=re.IGNORECASE).strip()
    # Strip trailing junk characters
    name = re.sub(r"[�é]+$", "", name).strip()
    # Collapse internal whitespace
    name = re.sub(r"\s{2,}", " ", name)
    return name

def apply_rules(name):
    name = clean_name(name)
    return REPLACEMENTS.get(name, name)

# ── Step 2: re-fetch partial/city-only names ──────────────────────────────────
# These arise when h2 parsing captured only the last comma-segment (a city).
PARTIAL_NAMES = {
    "Hong Kong", "Sweden", "Boston", "Urbana-Champaign", "Omaha",
    "Madison", "San Diego", "Ontario", "Newark", "Merced", "MI",
    "Lincoln", "Minnesota", "Bloomington", "Knoxville", "Grand Forks",
    "College Park", "St. Louis", "Colorado Springs", "Long Beach",
    "Scarborough Campus", "Okanagan", "UK", "Taiwan", "Norway",
}

def fetch_institution(session, job_id, retries=3):
    """Re-fetch the job page and return a clean institution name."""
    for attempt in range(retries):
        try:
            r = session.get(f"{JOB_URL}{job_id}", timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            # Try the structured location field first
            for tr in soup.find_all("tr", class_="prop"):
                n = tr.find("td", class_="name")
                v = tr.find("td", class_="value")
                if n and v and "institution" in n.get_text().lower():
                    val = re.sub(r"\s+", " ", v.get_text()).strip()
                    if val: return val
            # Fall back to h2 — take everything before the first comma as department,
            # then work backwards to find the institution
            h2 = soup.find("h2")
            if h2:
                raw = re.sub(r"\s+", " ", h2.get_text()).strip()
                # PhilJobs h2 format: "Dept, Institution" or "Institution"
                # If >1 comma segment, try second-to-last as institution
                parts = [p.strip() for p in raw.split(",")]
                if len(parts) >= 2:
                    return parts[-1]
                return raw
        except requests.RequestException:
            if attempt < retries - 1: time.sleep(4)
    return None


def main():
    session = requests.Session(); session.headers.update(HEADERS)

    rows = []
    with open(DETAIL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    changes = {}
    refetched = {}

    for row in rows:
        original = row["institution"]
        normalized = apply_rules(original)

        # If still a partial name, re-fetch
        if normalized in PARTIAL_NAMES:
            jid = int(row["job_id"])
            if jid not in refetched:
                fetched = fetch_institution(session, jid)
                if fetched:
                    refetched[jid] = apply_rules(fetched)
                    print(f"  Re-fetched job {jid}: '{original}' -> '{refetched[jid]}'")
                time.sleep(0.5)
            if jid in refetched:
                normalized = refetched[jid]

        if normalized != original:
            changes[original] = normalized
        row["institution"] = normalized

    # Write updated CSV
    with open(DETAIL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)

    print(f"\nNormalization complete. {len(changes)} distinct name variants corrected.")
    print("\nMappings applied:")
    for old, new in sorted(changes.items()):
        n_affected = sum(1 for r in rows if r["institution"] == new and old != new)
        print(f"  '{old}' → '{new}'")

    # Show new top institutions
    from collections import Counter
    insts = Counter(r["institution"] for r in rows)
    print("\nTop 20 institutions after normalization:")
    for inst, n in insts.most_common(20):
        print(f"  {n:>3}  {inst}")


if __name__ == "__main__":
    main()
