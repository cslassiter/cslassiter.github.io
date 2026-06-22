"""
philjobs_ai_audit.py

Estimates false-positive and false-negative rates for the AI job scrape.

FALSE POSITIVE AUDIT
  Sample ~80 jobs stratified by year from philjobs_ai_jobs_detail.csv.
  Fetch each page; check with a broad AI regex (broader than the original
  scraper, to catch any AI phrasing including newer terms).
  Estimate FP rate + 95% Wilson CI.

FALSE NEGATIVE AUDIT
  Re-use the non-Pass-1 sample job IDs already collected during the
  phil-tech recall analysis (philjobs_philtech_sample.csv).
  Exclude any IDs already in the AI dataset (they would be true positives).
  Fetch remaining pages; check with the broad AI regex.
  Estimate FN rate + 95% Wilson CI, and extrapolate to per-year counts.

Outputs
  philjobs_ai_audit_fp.csv    false-positive sample results
  philjobs_ai_audit_fn.csv    false-negative sample results
  (summary printed to stdout)
"""

import csv, random, re, time, requests, math
from pathlib import Path
from collections import defaultdict
from bs4 import BeautifulSoup

BASE_DIR   = Path(__file__).parent
DETAIL_CSV = BASE_DIR / "philjobs_ai_jobs_detail.csv"
SAMPLE_CSV = BASE_DIR / "philjobs_philtech_sample.csv"   # non-AI sample from phil-tech audit
AI_YEAR_CSV = BASE_DIR / "philjobs_ai_by_year.csv"
FP_CSV     = BASE_DIR / "philjobs_ai_audit_fp.csv"
FN_CSV     = BASE_DIR / "philjobs_ai_audit_fn.csv"
JOB_URL    = "https://philjobs.org/job/show/"

SAMPLE_PER_YEAR_FP = 6   # ~6 per year × 14 years ≈ 84 jobs for FP audit
random.seed(99)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── Broad AI regex (used for full-page verification) ─────────────────────────
# Deliberately wider than the original scraper to catch newer terminology
# and avoid false confirmation of vague passes.

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
# Case-sensitive patterns that must not be IGNORECASE
AI_VERIFY_CS = re.compile(r"\bAI\b|\bLLM\b|\bNLP\b|\bGPT\b")


def mentions_ai(text):
    if not text:
        return False, []
    hits = AI_VERIFY_RE.findall(text) + AI_VERIFY_CS.findall(text)
    return bool(hits), list(set(h.lower() for h in hits))


def fetch_text(session, job_id, retries=3):
    url = f"{JOB_URL}{job_id}"
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml").get_text(separator=" ", strip=True)
        except requests.RequestException as e:
            print(f"    Job {job_id} error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(4)
    return None


def wilson_ci(hits, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = hits / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1-p) / n + z**2 / (4 * n**2)) / denom
    return p, max(0, centre - margin), min(1, centre + margin)


def load_done(path):
    done = set()
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(int(row["job_id"]))
    return done


def append_rows(path, fieldnames, rows):
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerows(rows)


# ── Load AI job IDs ───────────────────────────────────────────────────────────

def load_ai_ids():
    ids = set()
    with open(AI_YEAR_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for jid in (row.get("ai_job_ids") or "").split("|"):
                if jid.strip():
                    ids.add(int(jid))
    return ids


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    all_ai_ids = load_ai_ids()
    session = requests.Session()
    session.headers.update(HEADERS)

    # ── FALSE POSITIVE AUDIT ─────────────────────────────────────────────────

    print("\n" + "="*65)
    print("FALSE POSITIVE AUDIT")
    print("="*65)

    # Load AI jobs; stratified sample by year
    by_year = defaultdict(list)
    with open(DETAIL_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_year[int(row["year"])].append(int(row["job_id"]))

    fp_sample_ids = set()
    for yr, ids in sorted(by_year.items()):
        n = min(SAMPLE_PER_YEAR_FP, len(ids))
        fp_sample_ids |= set(random.sample(ids, n))

    done_fp = load_done(FP_CSV)
    fp_sample_ids -= done_fp
    fp_fields = ["job_id", "year", "is_ai", "fetch_ok", "matched_terms"]

    # Load previously done results
    fp_results = []
    if FP_CSV.exists():
        with open(FP_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["is_ai"]    = row["is_ai"]    == "True"
                row["fetch_ok"] = row["fetch_ok"] == "True"
                fp_results.append(row)

    yr_lookup = {}
    with open(DETAIL_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yr_lookup[int(row["job_id"])] = int(row["year"])

    print(f"Sampling {len(fp_sample_ids)} new AI jobs (total target ~{SAMPLE_PER_YEAR_FP*14})...")
    new_fp = []
    for i, jid in enumerate(sorted(fp_sample_ids), 1):
        if i % 20 == 0:
            print(f"  {i}/{len(fp_sample_ids)}...")
        text = fetch_text(session, jid)
        is_ai, terms = mentions_ai(text)
        row = {
            "job_id":        jid,
            "year":          yr_lookup.get(jid, ""),
            "is_ai":         is_ai,
            "fetch_ok":      text is not None,
            "matched_terms": "|".join(terms),
        }
        fp_results.append(row)
        new_fp.append(row)
        time.sleep(0.6)

    append_rows(FP_CSV, fp_fields, new_fp)

    # Compute FP rate
    fp_fetchable = [r for r in fp_results if r["fetch_ok"] or str(r["fetch_ok"]) == "True"]
    fp_confirmed = [r for r in fp_fetchable if r["is_ai"] or str(r["is_ai"]) == "True"]
    n_fp_total   = len(fp_fetchable)
    n_fp_hit     = len(fp_confirmed)
    n_fp_miss    = n_fp_total - n_fp_hit      # jobs flagged as AI but no AI found on page

    fp_rate, fp_lo, fp_hi = wilson_ci(n_fp_miss, n_fp_total)

    print(f"\nFP audit: {n_fp_total} jobs fetched")
    print(f"  Confirmed AI on page: {n_fp_hit} ({n_fp_hit/n_fp_total*100:.1f}%)")
    print(f"  NO AI found on page:  {n_fp_miss} ({n_fp_miss/n_fp_total*100:.1f}%)")
    print(f"  Estimated FP rate: {fp_rate:.1%}  95% CI [{fp_lo:.1%}, {fp_hi:.1%}]")
    print(f"  => Estimated false positives in full dataset (586): "
          f"{round(fp_rate*586)}  [{round(fp_lo*586)}, {round(fp_hi*586)}]")

    # Show any unconfirmed jobs grouped by institution
    unconfirmed = [r for r in fp_fetchable
                   if not (r["is_ai"] or str(r["is_ai"]) == "True")]
    if unconfirmed:
        print(f"\n  Jobs with NO AI found on page ({len(unconfirmed)}):")
        inst_lookup = {}
        with open(DETAIL_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                inst_lookup[int(row["job_id"])] = row["institution"]
        for r in unconfirmed:
            jid = int(r["job_id"])
            print(f"    Job {jid} ({r['year']}) — {inst_lookup.get(jid, '?')}")

    # ── FALSE NEGATIVE AUDIT ─────────────────────────────────────────────────

    print("\n" + "="*65)
    print("FALSE NEGATIVE AUDIT")
    print("="*65)

    # Load non-AI sample jobs from phil-tech recall (already fetched)
    fn_candidates = []
    if SAMPLE_CSV.exists():
        with open(SAMPLE_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                jid = int(row["job_id"])
                # Exclude jobs already in the AI dataset
                if jid not in all_ai_ids:
                    fn_candidates.append((jid, int(row["year"])))
    else:
        print(f"  WARNING: {SAMPLE_CSV} not found — skipping FN audit.")
        return

    print(f"Non-AI sample jobs available: {len(fn_candidates)} "
          f"(after excluding known AI job IDs)")

    done_fn = load_done(FN_CSV)
    to_fetch_fn = [(jid, yr) for jid, yr in fn_candidates if jid not in done_fn]

    fn_results = []
    if FN_CSV.exists():
        with open(FN_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["is_ai"]    = row["is_ai"]    == "True"
                row["fetch_ok"] = row["fetch_ok"] == "True"
                fn_results.append(row)

    fn_fields = ["job_id", "year", "is_ai", "fetch_ok", "matched_terms"]

    print(f"Fetching {len(to_fetch_fn)} new non-AI sample pages...")
    new_fn = []
    for i, (jid, yr) in enumerate(to_fetch_fn, 1):
        if i % 50 == 0:
            print(f"  {i}/{len(to_fetch_fn)}...")
        text = fetch_text(session, jid)
        is_ai, terms = mentions_ai(text)
        row = {
            "job_id":        jid,
            "year":          yr,
            "is_ai":         is_ai,
            "fetch_ok":      text is not None,
            "matched_terms": "|".join(terms),
        }
        fn_results.append(row)
        new_fn.append(row)
        time.sleep(0.6)

    append_rows(FN_CSV, fn_fields, new_fn)

    fn_fetchable = [r for r in fn_results if r["fetch_ok"] or str(r["fetch_ok"]) == "True"]
    fn_hits      = [r for r in fn_fetchable if r["is_ai"] or str(r["is_ai"]) == "True"]
    n_fn_total   = len(fn_fetchable)
    n_fn_hits    = len(fn_hits)

    fn_rate, fn_lo, fn_hi = wilson_ci(n_fn_hits, n_fn_total)

    print(f"\nFN audit: {n_fn_total} non-AI-flagged jobs fetched")
    print(f"  AI found on page: {n_fn_hits} ({n_fn_hits/n_fn_total*100:.1f}%)")
    print(f"  Estimated FN rate: {fn_rate:.1%}  95% CI [{fn_lo:.1%}, {fn_hi:.1%}]")

    # Extrapolate missed jobs per year
    print(f"\n  Per-year false negative estimates:")
    total_by_year = {}
    with open(AI_YEAR_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total_by_year[int(row["year"])] = int(row["total_jobs"])
    ai_by_year = defaultdict(int)
    with open(DETAIL_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ai_by_year[int(row["year"])] += 1

    print(f"  {'Year':>6}  {'Non-AI jobs':>11}  {'Est. missed':>12}  {'Lo':>6}  {'Hi':>6}")
    print(f"  {'-'*50}")
    total_missed_lo = total_missed_hi = total_missed = 0
    for yr in sorted(total_by_year):
        non_ai = total_by_year[yr] - ai_by_year[yr]
        missed    = round(fn_rate * non_ai)
        missed_lo = round(fn_lo   * non_ai)
        missed_hi = round(fn_hi   * non_ai)
        total_missed    += missed
        total_missed_lo += missed_lo
        total_missed_hi += missed_hi
        print(f"  {yr:>6}  {non_ai:>11}  {missed:>12}  {missed_lo:>6}  {missed_hi:>6}")

    print(f"\n  Total estimated missed AI jobs across all years:")
    print(f"    Point estimate: {total_missed}")
    print(f"    95% CI: [{total_missed_lo}, {total_missed_hi}]")

    n_confirmed = len([r for r in fp_fetchable if r["is_ai"] or str(r["is_ai"]) == "True"])
    est_true_ai  = round(n_confirmed / n_fp_total * 586)
    print(f"\n  Show any flagged non-AI jobs with AI found on page:")
    for r in fn_hits[:10]:
        print(f"    Job {r['job_id']} ({r['year']}) — terms: {r['matched_terms']}")

    print("\nOutputs:")
    print(f"  {FP_CSV}")
    print(f"  {FN_CSV}")


if __name__ == "__main__":
    main()
