"""
pipelines/normalise.py
Builds a canonical ingredient list by matching FlavorDB names to USDA
Foundation Foods entries and counting Food.com recipe appearances.

Matching strategy:
  1. Exact match on USDA root name (everything before the first comma)
     e.g. "Butter" matches "Butter, stick, salted" via root "Butter"
  2. Fuzzy match on root name using character-level ratio (not substring)
     e.g. "Buttermilk" matches "Buttermilk, low fat" via root "Buttermilk"

No hardcoded mappings — all matching is automatic.

Output: data/processed/canonical_ingredients.csv
"""
import sys, ast
from pathlib import Path
import pandas as pd
from rapidfuzz import process, fuzz

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_PROC, FLAVORDB_ENTITIES_CSV, USDA_FOOD_CSV, FOODCOM_RECIPES

OUT_FILE       = DATA_PROC / "canonical_ingredients.csv"
FUZZY_THRESHOLD = 85   # minimum score for fuzzy root matching


# ── Step 1: load FlavorDB entities as the canonical list ─────────────────────

def load_canonical() -> pd.DataFrame:
    df = pd.read_csv(FLAVORDB_ENTITIES_CSV,
                     usecols=["entity_id","entity_alias_readable","category"])
    df = df.rename(columns={
        "entity_alias_readable": "canonical_name",
        "entity_id":             "flavordb_entity_id",
        "category":              "flavordb_category",
    })
    df["canonical_name_lower"] = df["canonical_name"].str.lower().str.strip()
    return df


# ── Step 2: match to USDA Foundation Foods via root name ─────────────────────

def match_usda(canonical: pd.DataFrame) -> pd.DataFrame:
    USDA_INGREDIENTS_CSV = DATA_PROC / "usda_ingredients.csv"
    if not USDA_INGREDIENTS_CSV.exists():
        print("  usda_ingredients.csv not found — run usda.py first")
        canonical["usda_fdc_id"]      = None
        canonical["usda_description"] = None
        canonical["usda_category"]    = None
        canonical["usda_match_score"] = None
        return canonical

    foundation = pd.read_csv(USDA_INGREDIENTS_CSV)
    # Rename ingredient to description to match existing logic
    foundation = foundation.rename(columns={"ingredient": "description"})

    # 1. root: "Butter, stick" -> "butter"
    # 2. uninverted: "Oil, olive" -> "olive oil"
    foundation["desc_lower"] = foundation["description"].str.lower().str.strip()
    foundation["root"]       = foundation["desc_lower"].str.split(",").str[0].str.strip()
    
    def uninvert(text):
        parts = [p.strip() for p in text.split(",")]
        if len(parts) > 1:
            return f"{parts[1]} {parts[0]}"
        return parts[0]
        
    foundation["uninverted"] = foundation["desc_lower"].apply(uninvert)

    print(f"  {len(foundation)} Foundation Foods")

    usda_fdc_ids, usda_descs, usda_categories, usda_scores = [], [], [], []
    exact_count = fuzzy_count = 0

    roots = foundation["root"].tolist()
    uninverteds = foundation["uninverted"].tolist()
    
    # We will match against uninverted strings using WRatio
    search_list = foundation["uninverted"].tolist()
    search_index = foundation.reset_index(drop=True)

    for name_lower in canonical["canonical_name_lower"]:

        # 1 — exact root match OR exact uninverted match
        exact = foundation[(foundation["root"] == name_lower) | (foundation["uninverted"] == name_lower)]
        if not exact.empty:
            row = exact.iloc[0]
            usda_fdc_ids.append(int(row["fdc_id"]))
            usda_descs.append(row["description"])
            usda_categories.append(row["category"])
            usda_scores.append(100)
            exact_count += 1
            continue

        # 2 — fuzzy match using WRatio on uninverted string
        # WRatio handles partial matches and different token orders much better than basic ratio
        result = process.extractOne(
            name_lower, search_list,
            scorer=fuzz.WRatio,
            score_cutoff=FUZZY_THRESHOLD
        )
        if result:
            matched_str, score, idx = result
            row = search_index.iloc[idx]
            usda_fdc_ids.append(int(row["fdc_id"]))
            usda_descs.append(row["description"])
            usda_categories.append(row["category"])
            usda_scores.append(round(score, 2))
            fuzzy_count += 1
            continue

        usda_fdc_ids.append(None)
        usda_descs.append(None)
        usda_categories.append(None)
        usda_scores.append(None)

    canonical["usda_fdc_id"]      = usda_fdc_ids
    canonical["usda_description"] = usda_descs
    canonical["usda_category"]    = usda_categories
    canonical["usda_match_score"] = usda_scores

    total = exact_count + fuzzy_count
    print(f"  Exact: {exact_count} | Fuzzy: {fuzzy_count} | Total: {total}/{len(canonical)}")

    sample = canonical[canonical["usda_fdc_id"].notna()][
        ["canonical_name","usda_description","usda_match_score"]
    ].head(30)
    print(sample.to_string(index=False))
    return canonical


# ── Step 3: count Food.com recipe appearances ─────────────────────────────────

def match_foodcom(canonical: pd.DataFrame) -> pd.DataFrame:
    if not FOODCOM_RECIPES.exists():
        print("  RAW_recipes.csv not found — skipping")
        canonical["foodcom_recipe_count"] = None
        return canonical

    print("  Counting Food.com recipe appearances...")
    recipes = pd.read_csv(FOODCOM_RECIPES, usecols=["ingredients"])
    counts  = {name: 0 for name in canonical["canonical_name_lower"]}

    for raw in recipes["ingredients"]:
        try:
            ingredients = ast.literal_eval(raw)
            text = " ".join(ingredients).lower()
            for name in counts:
                if name in text:
                    counts[name] += 1
        except Exception:
            continue

    canonical["foodcom_recipe_count"] = canonical["canonical_name_lower"].map(counts)
    top = max(counts, key=counts.get)
    print(f"  Done. Top: '{top}' ({counts[top]:,} recipes)")
    return canonical


# ── Run ───────────────────────────────────────────────────────────────────────

def run():
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    print("Step 1: Loading FlavorDB canonical list...")
    canonical = load_canonical()
    print(f"  {len(canonical)} canonical ingredients")

    print("\nStep 2: Matching to USDA Foundation Foods...")
    canonical = match_usda(canonical)

    print("\nStep 3: Counting Food.com appearances...")
    canonical = match_foodcom(canonical)

    canonical = canonical.drop(columns=["canonical_name_lower"])
    canonical.to_csv(OUT_FILE, index=False)

    print(f"\nSaved -> {OUT_FILE}")
    print(f"\nSummary:")
    print(f"  Total canonical ingredients : {len(canonical)}")
    print(f"  Matched to USDA             : {canonical['usda_fdc_id'].notna().sum()}")
    print(f"  With Food.com data          : {canonical['foodcom_recipe_count'].notna().sum()}")

    print(f"\nTop 10 by Food.com recipe count:")
    print(canonical.sort_values("foodcom_recipe_count", ascending=False)
                   [["canonical_name","flavordb_category",
                     "usda_description","foodcom_recipe_count"]]
                   .head(10).to_string(index=False))

    name_list = OUT_FILE.parent / "canonical_names.txt"
    canonical["canonical_name"].to_csv(name_list, index=False, header=False)
    print(f"\nName list -> {name_list}")


if __name__ == "__main__":
    run()
