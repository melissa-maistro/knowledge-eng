"""
pipelines/curated_allergens.py
Builds ingredient-level allergen triples from curated mappings rather than
Open Food Facts product labels. OFF data reflects cross-contamination in
packaged goods, not the intrinsic allergen class of whole ingredients, and
produces too many false positives for clinical use.

Coverage targets the EU Big 14 allergens most relevant to dietetics:
  gluten, dairy, eggs, fish, shellfish, molluscs, tree_nuts, peanuts,
  soy, sesame, mustard, celery, lupin, sulphites

Output: data/triples/allergens.csv  (replaces the OFF-based file)
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_PROC, TRIPLE_ALLERGENS

CANONICAL_FILE = DATA_PROC / "canonical_ingredients.csv"

# ── Category → allergen(s) ────────────────────────────────────────────────────
# FlavorDB categories that unambiguously map to an allergen class.
CATEGORY_ALLERGENS = {
    "dairy":             ["dairy"],
    "fishseafood-fish":  ["fish"],
}

# fishseafood-seafood mixes crustaceans, molluscs, and other sea life —
# handled explicitly below.
CRUSTACEANS = {
    "Crab", "Crayfish", "Krill", "Lobster", "Prawn", "Shrimp",
    "Spiny lobster", "Shellfish", "Trassi",
}
MOLLUSCS = {
    "Clam", "Mollusc", "Oyster", "Scallop", "Squid",
    "Common octopus", "North Pacific giant octopus", "Whelk",
    "Bivalvia", "Leather chiton",
}

# nutseed-nut: all are tree nuts
CATEGORY_ALLERGENS["nutseed-nut"] = ["tree_nuts"]

# ── Gluten-containing grains (cerealcrop-cereal sub-set) ─────────────────────
# Rice, Quinoa, Sorghum, Teff, Buckwheat, and Wild rice are gluten-free.
GLUTEN_GRAINS = {
    "Wheat", "Hard wheat", "Oriental wheat", "Spelt", "Rye",
    "Barley", "Malt", "Oats", "Triticale", "Flour",
    "Crispbread", "Sourdough", "Bulgur",
}

# ── Name-based mappings for ingredients whose allergen isn't captured above ──
# Key: canonical_name (exact, case-sensitive)  Value: list of allergen strings
NAME_ALLERGENS: dict[str, list[str]] = {
    # Eggs
    "Egg":              ["eggs"],
    "Egg White":        ["eggs"],
    "Egg Yolk":         ["eggs"],
    # Peanuts  (nutseed-legume, not nut)
    "Peanut":           ["peanuts"],
    "Peanut Oil":       ["peanuts"],
    "Peanut Butter":    ["peanuts"],
    # Soy  (nutseed-legume)
    "Soybean":          ["soy"],
    "Soybean Oil":      ["soy"],
    "Tofu":             ["soy"],
    "Tempeh":           ["soy"],
    "Miso":             ["soy"],
    "Natto":            ["soy"],
    "Edamame":          ["soy"],
    "Soy milk":         ["soy"],
    # Sesame  (nutseed-seed)
    "Sesame":           ["sesame"],
    "Tahini":           ["sesame"],
    # Mustard
    "Mustard":          ["mustard"],
    "Mustard Oil":      ["mustard"],
    # Celery
    "Celery":           ["celery"],
    "Celeriac":         ["celery"],
    # Lupin
    "Lupin":            ["lupin"],
    "Lupine":           ["lupin"],
    # Sulphites  (commonly in dried fruits and wine)
    "Dried Fruit":      ["sulphites"],
    "Wine":             ["sulphites"],
    "Red Wine":         ["sulphites"],
    "White Wine":       ["sulphites"],
    "Sherry":           ["sulphites"],
}


def run():
    if not CANONICAL_FILE.exists():
        print("canonical_ingredients.csv not found — run normalise.py first")
        return

    canon = pd.read_csv(CANONICAL_FILE)
    rows = []

    for _, row in canon.iterrows():
        name = str(row["canonical_name"]).strip()
        cat  = str(row.get("flavordb_category", "")).strip()
        allergens: set[str] = set()

        # 1. Category-based rules
        if cat in CATEGORY_ALLERGENS:
            allergens.update(CATEGORY_ALLERGENS[cat])

        # 2. fishseafood-seafood: classify by name
        if cat == "fishseafood-seafood":
            if name in CRUSTACEANS:
                allergens.add("shellfish")
            elif name in MOLLUSCS:
                allergens.add("molluscs")

        # 3. Gluten grains
        if name in GLUTEN_GRAINS:
            allergens.add("gluten")

        # 4. Name-based overrides / additions
        if name in NAME_ALLERGENS:
            allergens.update(NAME_ALLERGENS[name])

        for allergen in allergens:
            rows.append({
                "subject":  name,
                "relation": "HAS_ALLERGEN",
                "object":   allergen,
            })

    out = pd.DataFrame(rows).drop_duplicates()
    TRIPLE_ALLERGENS.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(TRIPLE_ALLERGENS, index=False)

    print(f"Curated allergen triples written: {len(out)}")
    print(f"Ingredients with allergen data: {out['subject'].nunique()}")
    print(f"\nAllergen breakdown:")
    print(out["object"].value_counts().to_string())
    print(f"\nSample — Butter: {out[out.subject=='Butter']['object'].tolist()}")
    print(f"Sample — Almond: {out[out.subject=='Almond']['object'].tolist()}")
    print(f"Sample — Wheat:  {out[out.subject=='Wheat']['object'].tolist()}")
    print(f"Sample — Shrimp: {out[out.subject=='Shrimp']['object'].tolist()}")
    print(f"Sample — Apple:  {out[out.subject=='Apple']['object'].tolist()}")
    print(f"\n-> {TRIPLE_ALLERGENS}")


if __name__ == "__main__":
    run()
