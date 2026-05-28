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
from config import DATA_PROC, FLAVORDB_ENTITIES_CSV, USDA_FOOD_CSV, FOODCOM_RECIPES, TRIPLE_NUTRIENTS

OUT_FILE       = DATA_PROC / "canonical_ingredients.csv"
FUZZY_THRESHOLD = 85   # minimum score for fuzzy root matching (using token_sort_ratio)


# ── Step 1: load FlavorDB entities as the canonical list ─────────────────────

# FlavorDB categories that are not whole ingredients and must be excluded.
# "dish"        — prepared meals (Burrito, Pizza, Lasagna, Hamburger…)
# "essentialoil" — industrial flavor extracts not used in home cooking
NON_INGREDIENT_CATEGORIES = {"dish", "essentialoil"}

# FlavorDB entity names that are category/group labels or taxonomic names,
# not specific ingredients a patient would use in a recipe.
NON_INGREDIENT_NAMES = {
    # Generic category labels
    "Bakery Products", "Dairy Products", "Fish", "Meat", "Shellfish", "Beans",
    "Nuts", "Mixed nuts",
    # Vague aggregate groups
    "Fatty Fish", "Lean Fish", "Smoked Fish", "Other Cheeses",
    "Other meat product", "Other fish product", "Other fermented milk",
    "Other bread product",
    # Scientific taxonomy / fish family names (not ingredient names)
    "Salmonidae", "Clupeinae", "Percoidei", "Perciformes", "Bivalvia",
    "Anguilliformes", "Gadiformes", "Scombridae", "Pleuronectidae",
    "Cetacea", "Cichlidae",
}


def load_canonical() -> pd.DataFrame:
    df = pd.read_csv(FLAVORDB_ENTITIES_CSV,
                     usecols=["entity_id","entity_alias_readable","category"])
    df = df.rename(columns={
        "entity_alias_readable": "canonical_name",
        "entity_id":             "flavordb_entity_id",
        "category":              "flavordb_category",
    })
    before = len(df)
    df = df[~df["flavordb_category"].isin(NON_INGREDIENT_CATEGORIES)].copy()
    df = df[~df["canonical_name"].isin(NON_INGREDIENT_NAMES)].copy()
    print(f"  Excluded {before - len(df)} non-ingredient entries")
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

    MANUAL_OVERRIDES = {
        "olive": "oil, olive, extra virgin",
        "cooking oil": "oil, canola",
        "salad dressing": "salad dressing, italian dressing, commercial, regular",
        "pasta": "pasta, dry, enriched, spaghetti",
        "biscuit": "bread, white, commercial",
        "cheese": "cheese, american, restaurant",
        "beef": "beef, chuck, roast, boneless, choice, raw"
    }

    # Ingredients with no valid USDA match — skip fuzzy matching entirely
    # to prevent spurious matches (e.g. "white wine" → "cheese, dry white")
    NO_USDA_MATCH = {
        "white wine", "red wine", "wine", "beer", "champagne",
        "spirit", "liqueur", "vodka", "rum", "whiskey",
    }

    for name_lower in canonical["canonical_name_lower"]:
        # -1 — Explicit no-match list
        if name_lower in NO_USDA_MATCH:
            usda_fdc_ids.append(None)
            usda_descs.append(None)
            usda_categories.append(None)
            usda_scores.append(None)
            continue

        # 0 — Manual overrides
        if name_lower in MANUAL_OVERRIDES:
            exact = foundation[foundation["desc_lower"] == MANUAL_OVERRIDES[name_lower]]
            if not exact.empty:
                row = exact.iloc[0]
                usda_fdc_ids.append(int(row["fdc_id"]))
                usda_descs.append(row["description"])
                usda_categories.append(row["category"])
                usda_scores.append(100)
                exact_count += 1
                continue

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

        # 2 — fuzzy match using token_sort_ratio on uninverted string
        # token_sort_ratio is stricter than WRatio and prevents partial matches on "oil" from matching "anchovies"
        result = process.extractOne(
            name_lower, search_list,
            scorer=fuzz.token_sort_ratio,
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


# ── Step 4: Derive functional class from macronutrients ──────────────────────

FAT_KEY  = "Total lipid (fat)"
PROT_KEY = "Protein"
CARB_KEY = "Carbohydrate, by difference"

def derive_functional_class(canonical: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns a data-driven functional_class to each canonical ingredient that has
    USDA nutritional data, based on which macronutrient dominates its caloric profile:

        fat_source    : fat calories  >= 50% of total macro calories
        protein_source: protein cals  >= 30% of total macro calories
        carb_source   : carb calories >= 50% of total macro calories
        mixed         : no single macro dominates (e.g. nuts, eggs)

    Ingredients without USDA data get functional_class = None.
    The fallback in similarity.py will use flavordb_category for those.
    """
    if not TRIPLE_NUTRIENTS.exists():
        print("  nutrients.csv not found — skipping functional class derivation")
        canonical["functional_class"] = None
        return canonical

    nt = pd.read_csv(TRIPLE_NUTRIENTS)
    # Merge "Total fat (NLEA)" into FAT_KEY for subjects (e.g. pure oils)
    # that only report the NLEA fat value.
    nlea = nt[nt["relation_target"] == "Total fat (NLEA)"].copy()
    has_lipid = set(nt[nt["relation_target"] == FAT_KEY]["subject"])
    nlea = nlea[~nlea["subject"].isin(has_lipid)]
    nlea["relation_target"] = FAT_KEY
    nt = pd.concat([nt, nlea], ignore_index=True)
    macros = nt[nt["relation_target"].isin([FAT_KEY, PROT_KEY, CARB_KEY])].copy()

    pivot = macros.pivot_table(
        index="subject", columns="relation_target", values="amount", aggfunc="mean"
    ).fillna(0)
    pivot.columns.name = None
    pivot = pivot.rename(columns={FAT_KEY: "fat_g", PROT_KEY: "prot_g", CARB_KEY: "carb_g"})
    for col in ["fat_g", "prot_g", "carb_g"]:
        if col not in pivot.columns:
            pivot[col] = 0.0

    # Convert grams to kcal (fat=9, protein=4, carb=4)
    pivot["fat_kcal"]   = pivot["fat_g"]  * 9.0
    pivot["prot_kcal"]  = pivot["prot_g"] * 4.0
    pivot["carb_kcal"]  = pivot["carb_g"] * 4.0
    pivot["total_kcal"] = pivot["fat_kcal"] + pivot["prot_kcal"] + pivot["carb_kcal"]

    def classify(row):
        if row["total_kcal"] == 0:
            return None
        fat_pct  = row["fat_kcal"]  / row["total_kcal"]
        prot_pct = row["prot_kcal"] / row["total_kcal"]
        carb_pct = row["carb_kcal"] / row["total_kcal"]
        if fat_pct  >= 0.50: return "fat_source"
        if carb_pct >= 0.50: return "carb_source"
        if prot_pct >= 0.30: return "protein_source"
        return "mixed"

    pivot["functional_class"] = pivot.apply(classify, axis=1)
    usda_to_func = pivot["functional_class"].to_dict()  # key = USDA description string

    # Map back to canonical via usda_description column
    canonical["functional_class"] = canonical["usda_description"].map(usda_to_func)

    counts = canonical["functional_class"].value_counts(dropna=False)
    print("  Functional class distribution:")
    print(counts.to_string())
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

    print("\nStep 4: Deriving functional class from macronutrients...")
    canonical = derive_functional_class(canonical)

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
