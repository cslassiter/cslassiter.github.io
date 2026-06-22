import pandas as pd
import re
from collections import Counter
from pathlib import Path

# Reads the main job-level dataset from the same folder as this script.
df = pd.read_csv(Path(__file__).parent / 'philjobs_ai_jobs_detail.csv')

# ── AOS classification ──────────────────────────────────────────────────────

def classify_aos(text):
    """
    Assign one or more broad categories to an AOS string via keyword matching.
    Returns a list of matched categories (can be multi-label).
    """
    if pd.isna(text):
        return ['Open/Unspecified']
    t = text.lower()

    cats = []

    # Open / unspecified
    open_kw = [r'\bopen\b', r'no restriction', r'all areas', r'any area',
               r'see job description', r'not specified', r'^open$']
    if any(re.search(k, t) for k in open_kw):
        cats.append('Open/Unspecified')

    # Ethics / applied ethics / bioethics / moral philosophy
    ethics_kw = [r'\bethics\b', r'bioethics', r'moral phil', r'applied ethics',
                 r'normative', r'metaethics', r'meta-ethics', r'moral theory',
                 r'value theory', r'practical ethics', r'medical ethics',
                 r'business ethics', r'environmental ethics', r'neuroethics',
                 r'research ethics', r'data ethics', r'ai ethics',
                 r'responsible ai', r'fairness.*machine', r'algorithmic']
    if any(re.search(k, t) for k in ethics_kw):
        cats.append('Ethics/Applied Ethics')

    # Philosophy of Mind / Cognitive Science / AI/Robotics
    mind_kw = [r'philosophy of mind', r'cognitive sci', r'consciousness',
               r'philosophy of psychology', r'artificial intelligence',
               r'\bai\b', r'robotics', r'machine learning', r'deep learning',
               r'neural net', r'natural language', r'\bnlp\b', r'computer vision',
               r'knowledge representation', r'intelligent system',
               r'philosophy.*cognitive', r'mind.*cognition', r'perception',
               r'philosophy of action', r'intentionality', r'mental content',
               r'extended mind', r'embodied cognition', r'neuroscience.*phil',
               r'phil.*neuroscience', r'neurosc']
    if any(re.search(k, t) for k in mind_kw):
        cats.append('Phil. of Mind/Cog. Sci./AI')

    # Logic / Formal methods / Mathematics
    logic_kw = [r'\blogic\b', r'\blogics\b', r'formal method', r'formal epistem',
                r'modal logic', r'proof theory', r'set theory', r'model theory',
                r'mathematical logic', r'philosophy of math', r'phil.*mathemat',
                r'mathemat.*phil', r'formal semantic', r'type theory',
                r'computat.*phil', r'phil.*comput', r'protocol.*logic',
                r'knowledge representation and reasoning',
                r'theorem prov', r'automated reasoning']
    if any(re.search(k, t) for k in logic_kw):
        cats.append('Logic/Formal Methods')

    # Epistemology / Social Epistemology
    epist_kw = [r'epistemolog', r'knowledge.*theory', r'theory of knowledge',
                r'social epistem', r'testimony', r'peer disagreement',
                r'justified belief', r'rationality', r'scientific reasoning']
    if any(re.search(k, t) for k in epist_kw):
        cats.append('Epistemology')

    # Philosophy of Science / Technology / Data Science
    sci_kw = [r'philosophy of science', r'philosophy of biology',
              r'philosophy of physics', r'philosophy of chemistry',
              r'philosophy of technology', r'phil.*sci\b', r'sci.*philosophy',
              r'history.*science', r'science.*history', r'philosophy of medicine',
              r'philosophy of psychiatry', r'data science', r'information sci',
              r'science and technology', r'sts\b', r'biomedical',
              r'philosophy of social science', r'explanation', r'causation',
              r'causal inference', r'scientific method', r'philosophy of statistics',
              r'philosophy of ecology', r'evolutionary.*phil', r'phil.*evolution']
    if any(re.search(k, t) for k in sci_kw):
        cats.append('Phil. of Science/Technology')

    # Social / Political Philosophy
    soc_kw = [r'social phil', r'political phil', r'justice', r'democracy',
              r'distributive', r'rights', r'political theory', r'feminism',
              r'feminist phil', r'critical theory', r'race.*phil', r'phil.*race',
              r'phil.*gender', r'gender.*phil', r'diversity', r'inclusion',
              r'colonialism', r'decolonial', r'global justice',
              r'philosophy of law', r'legal phil', r'jurisprudence']
    if any(re.search(k, t) for k in soc_kw):
        cats.append('Social/Political Philosophy')

    # Metaphysics / Ontology
    meta_kw = [r'metaphysics', r'\bontology\b', r'ontolog', r'mereology',
               r'modality', r'persistence', r'personal identity', r'free will',
               r'philosophy of time', r'grounding', r'emergence']
    if any(re.search(k, t) for k in meta_kw):
        cats.append('Metaphysics/Ontology')

    # History of Philosophy / Asian / Continental
    hist_kw = [r'history of phil', r'hist.*phil', r'phil.*hist',
               r'ancient phil', r'medieval phil', r'early modern',
               r'kant\b', r'hegel\b', r'continental', r'phenomenolog',
               r'existential', r'asian phil', r'chinese phil', r'indian phil',
               r'buddhist phil', r'african phil', r'latin american']
    if any(re.search(k, t) for k in hist_kw):
        cats.append('History/Continental/Non-Western')

    # Language / Linguistics / Semantics / Pragmatics
    lang_kw = [r'philosophy of language', r'phil.*language', r'language.*phil',
               r'semantics', r'pragmatics', r'linguistic', r'meaning.*theory',
               r'theory.*meaning']
    if any(re.search(k, t) for k in lang_kw):
        cats.append('Philosophy of Language')

    if not cats:
        cats.append('Other/Unclassified')

    return cats

df['cats'] = df['aos'].apply(classify_aos)

# ── Region classification ────────────────────────────────────────────────────

def classify_region(loc):
    if pd.isna(loc):
        return 'Unknown'
    l = loc.lower()
    if 'united states' in l:
        return 'United States'
    if 'canada' in l:
        return 'Canada'
    if 'united kingdom' in l or 'england' in l or 'scotland' in l or 'wales' in l:
        return 'United Kingdom'
    if any(x in l for x in ['germany', 'france', 'netherlands', 'spain', 'italy',
                              'denmark', 'sweden', 'norway', 'finland', 'belgium',
                              'austria', 'switzerland', 'poland', 'portugal',
                              'czech', 'hungary', 'greece', 'ireland']):
        return 'Continental Europe'
    if any(x in l for x in ['hong kong', 'china', 'singapore', 'taiwan',
                              'japan', 'korea', 'india', 'thailand']):
        return 'Asia'
    if any(x in l for x in ['australia', 'new zealand']):
        return 'Australia/NZ'
    if any(x in l for x in ['israel', 'turkey', 'south africa', 'brazil',
                              'argentina', 'mexico', 'chile']):
        return 'Other'
    return 'Other'

df['region'] = df['location'].apply(classify_region)

# ── Explode to one row per category ─────────────────────────────────────────
df_exp = df.explode('cats')

# ── Period classification ────────────────────────────────────────────────────
df['year'] = pd.to_numeric(df['year'], errors='coerce')
df_exp['year'] = pd.to_numeric(df_exp['year'], errors='coerce')
df['period'] = df['year'].apply(lambda y: '2013-2019' if y <= 2019 else '2020-2026')
df_exp['period'] = df_exp['year'].apply(lambda y: '2013-2019' if y <= 2019 else '2020-2026')

total = len(df)

# ═══════════════════════════════════════════════════════════════════════════════
# Q4: Open/Unspecified proportion (based on original rows, single-label check)
# ═══════════════════════════════════════════════════════════════════════════════
open_count = df['cats'].apply(lambda c: 'Open/Unspecified' in c).sum()
print("=" * 70)
print(f"Q4 — Open/Unspecified AOS")
print("=" * 70)
print(f"  Open/Unspecified: {open_count} / {total} = {open_count/total*100:.1f}%")

# ═══════════════════════════════════════════════════════════════════════════════
# Q1: Overall category counts
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("Q1 — Overall AOS category distribution (multi-label; % of 601 jobs)")
print("=" * 70)
cat_counts = df_exp['cats'].value_counts()
print(f"{'Category':<40} {'Count':>6}  {'% of jobs':>9}")
print("-" * 60)
for cat, cnt in cat_counts.items():
    print(f"{cat:<40} {cnt:>6}  {cnt/total*100:>8.1f}%")

# ═══════════════════════════════════════════════════════════════════════════════
# Q2: Category by year
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("Q2 — AOS categories by year")
print("=" * 70)
year_cat = df_exp.groupby(['year', 'cats']).size().unstack(fill_value=0)
year_totals = df.groupby('year').size()
print("\nRaw counts per year (columns = categories):")
print(year_cat.to_string())

print("\n\nYear totals:")
print(year_totals.to_string())

# Two-period comparison
print("\n\nTwo-period comparison (counts; % of jobs in that period):")
period_cat = df_exp.groupby(['period', 'cats']).size().unstack(fill_value=0)
period_totals = df.groupby('period').size()
print(f"\n{'Category':<40} {'2013-2019':>15}  {'2020-2026':>15}")
print("-" * 72)
for cat in cat_counts.index:
    n1 = period_cat.loc['2013-2019', cat] if cat in period_cat.columns else 0
    n2 = period_cat.loc['2020-2026', cat] if cat in period_cat.columns else 0
    t1 = period_totals.get('2013-2019', 1)
    t2 = period_totals.get('2020-2026', 1)
    print(f"{cat:<40} {n1:>5} ({n1/t1*100:>4.1f}%)   {n2:>5} ({n2/t2*100:>4.1f}%)")

# ═══════════════════════════════════════════════════════════════════════════════
# Q3: Category by region
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("Q3 — AOS categories by region")
print("=" * 70)
region_totals = df.groupby('region').size().sort_values(ascending=False)
print("\nRegion totals:")
print(region_totals.to_string())

region_cat = df_exp.groupby(['region', 'cats']).size().unstack(fill_value=0)
print(f"\n{'Category':<40}", end='')
for reg in region_totals.index:
    print(f"  {reg[:12]:>12}", end='')
print()
print("-" * (40 + 14 * len(region_totals)))
for cat in cat_counts.index:
    print(f"{cat:<40}", end='')
    for reg in region_totals.index:
        n = region_cat.loc[reg, cat] if cat in region_cat.columns and reg in region_cat.index else 0
        t = region_totals[reg]
        print(f"  {n:>3}({n/t*100:>4.0f}%)", end='')
    print()

# ── Bonus: top raw AOS strings ───────────────────────────────────────────────
print("\n" + "=" * 70)
print("Bonus — Top 30 most frequent raw AOS strings")
print("=" * 70)
top_raw = df['aos'].value_counts().head(30)
print(top_raw.to_string())
