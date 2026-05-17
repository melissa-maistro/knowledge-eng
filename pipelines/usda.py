"""
pipelines/usda.py
Reads USDA FoodData Central CSVs and writes a nutrients triple file.
Filters to foundation_food only — clean whole-ingredient entries.
Reads food_nutrient.csv in chunks to handle large file sizes.

Download from: https://fdc.nal.usda.gov/download-datasets
Place food.csv, nutrient.csv, food_nutrient.csv, food_category.csv in data/raw/
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import USDA_FOOD_CSV, USDA_CATEGORY_CSV, USDA_NUTRIENT_CSV, USDA_FOOD_NUTRIENT_CSV, DATA_PROC, TRIPLE_NUTRIENTS


def load_nutrient_ids(nutrient_csv: Path) -> dict:
    """
    Load all nutrient IDs and names from nutrient.csv.
    Returns a dict of {nutrient_id: nutrient_name}.
    Filters to nutrients relevant for dietary counselling.
    """
    nutrients = pd.read_csv(nutrient_csv, usecols=["id","name","unit_name"])

    # keywords that indicate clinically relevant nutrients
    relevant_keywords = [
        "protein", "fat", "carbohydrate", "energy", "fiber", "fibre",
        "sodium", "calcium", "iron", "potassium", "vitamin c",
        "vitamin d", "saturated", "sugar", "cholesterol", "magnesium",
        "zinc", "folate", "vitamin b12", "vitamin a",
    ]

    mask = nutrients["name"].str.lower().apply(
        lambda n: any(kw in n for kw in relevant_keywords)
    )
    filtered = nutrients[mask]
    return dict(zip(filtered["id"], filtered["name"]))


def run():
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    # ── load foundation foods ─────────────────────────────────────────────────
    print("Loading USDA food descriptions and categories...")
    foods = pd.read_csv(USDA_FOOD_CSV, usecols=["fdc_id","description","data_type","food_category_id"])
    foods = foods[foods["data_type"] == "foundation_food"].copy()
    
    if USDA_CATEGORY_CSV.exists():
        categories = pd.read_csv(USDA_CATEGORY_CSV, usecols=["id", "description"]).rename(
            columns={"id": "food_category_id", "description": "category"}
        )
        # Convert both to float to avoid dtype mismatch
        foods["food_category_id"] = pd.to_numeric(foods["food_category_id"], errors="coerce")
        categories["food_category_id"] = pd.to_numeric(categories["food_category_id"], errors="coerce")
        foods = foods.merge(categories, on="food_category_id", how="left")
        foods["category"] = foods["category"].fillna("Unknown")
    else:
        print(f"  {USDA_CATEGORY_CSV} not found, skipping categories.")
        foods["category"] = "Unknown"
        
    print(f"  {len(foods)} foundation foods loaded")

    if foods.empty:
        print("  No foundation_food entries found — check your food.csv")
        return

    fdc_ids = set(foods["fdc_id"])

    # ── load relevant nutrient IDs from nutrient.csv ──────────────────────────
    print("Loading nutrient definitions...")
    if not USDA_NUTRIENT_CSV.exists():
        print(f"  nutrient.csv not found at {USDA_NUTRIENT_CSV}")
        print("  Falling back to food_nutrient.csv without nutrient name filtering")
        keep_nutrients = None
    else:
        keep_nutrients = load_nutrient_ids(USDA_NUTRIENT_CSV)
        print(f"  {len(keep_nutrients)} relevant nutrients identified")

    # ── read food_nutrient.csv in chunks ──────────────────────────────────────
    print("Loading food_nutrient.csv in chunks...")
    chunks = []
    total  = 0

    read_cols = ["fdc_id","nutrient_id","amount"]

    for chunk in pd.read_csv(
        USDA_FOOD_NUTRIENT_CSV,
        usecols=read_cols,
        chunksize=200_000
    ):
        # filter to our foods first (biggest reduction)
        chunk = chunk[chunk["fdc_id"].isin(fdc_ids)]

        # then filter to relevant nutrients if we have the list
        if keep_nutrients:
            chunk = chunk[chunk["nutrient_id"].isin(keep_nutrients)]

        if not chunk.empty:
            chunks.append(chunk)

        total += 200_000
        print(f"  Processed {total:,} rows...", end="\r")

    if not chunks:
        print("\n  No matching nutrient data found — check food_nutrient.csv")
        return

    fn = pd.concat(chunks, ignore_index=True)
    print(f"\n  Done. {len(fn)} relevant nutrient rows kept")

    # map nutrient_id to name if available
    if keep_nutrients:
        fn["nutrient"] = fn["nutrient_id"].map(keep_nutrients)
    else:
        fn["nutrient"] = fn["nutrient_id"].astype(str)

    # ── merge and aggregate ───────────────────────────────────────────────────
    merged = fn.merge(foods[["fdc_id","description","category"]], on="fdc_id")
    merged = merged[["fdc_id","description","category","nutrient","amount"]].dropna()
    merged.columns = ["fdc_id","ingredient","category","nutrient","amount_per_100g"]

    # Deduplicate entries with exact same description by averaging the nutrients
    print("Aggregating duplicates by taking the mean of nutrients...")
    grouped = merged.groupby(["ingredient", "category", "nutrient"], as_index=False).agg({
        "amount_per_100g": "mean",
        "fdc_id": "first"  # keep the first ID for reference
    })
    merged = grouped[["fdc_id", "ingredient", "category", "nutrient", "amount_per_100g"]]
    
    # Save a clean ingredients list with categories
    ingredients_df = grouped[["fdc_id", "ingredient", "category"]].drop_duplicates()
    ing_out = DATA_PROC / "usda_ingredients.csv"
    ingredients_df.to_csv(ing_out, index=False)
    print(f"  Saved {len(ingredients_df)} unique ingredients to {ing_out}")

    out = DATA_PROC / "usda_nutrients.csv"
    merged.to_csv(out, index=False)

    # write triples: (ingredient) -[HAS_NUTRIENT {amount}]-> (nutrient)
    TRIPLE_NUTRIENTS.parent.mkdir(parents=True, exist_ok=True)
    triples = merged.rename(columns={
        "ingredient":      "subject",
        "nutrient":        "relation_target",
        "amount_per_100g": "amount"
    })
    triples["relation"] = "HAS_NUTRIENT"
    triples[["subject","relation","relation_target","amount","fdc_id"]].to_csv(
        TRIPLE_NUTRIENTS, index=False
    )

    print(f"  {len(foods)} foods | {len(merged)} nutrient rows")
    print(f"  -> {out}")
    print(f"  -> {TRIPLE_NUTRIENTS}")

    # print sample for inspection
    print(f"\nSample nutrients for first matched food:")
    first = merged["ingredient"].iloc[0]
    print(merged[merged["ingredient"] == first][["nutrient","amount_per_100g"]].to_string(index=False))


if __name__ == "__main__":
    run()
