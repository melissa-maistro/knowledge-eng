"""
pipelines/openfoodfacts.py
Extracts allergen data from Open Food Facts bulk CSV.

Download first:
  https://world.openfoodfacts.org/data
  -> en.openfoodfacts.org.products.csv.gz  (~9 GB uncompressed)
  -> Place in data/raw/
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OFF_CSV, DATA_PROC, TRIPLE_ALLERGENS

ALLERGEN_COLS = ["allergens_en", "traces_en"]

# Normalise the messy tag strings to a fixed allergen vocabulary
ALLERGEN_NORMALISE = {
    "gluten": "gluten", "wheat": "gluten", "rye": "gluten", "barley": "gluten",
    "milk": "dairy", "dairy": "dairy", "lactose": "dairy",
    "eggs": "eggs", "egg": "eggs",
    "nuts": "tree_nuts", "tree-nuts": "tree_nuts", "almonds": "tree_nuts",
    "cashews": "tree_nuts", "walnuts": "tree_nuts",
    "peanuts": "peanuts", "peanut": "peanuts",
    "soy": "soy", "soybeans": "soy", "soya": "soy",
    "fish": "fish", "shellfish": "shellfish", "crustaceans": "shellfish",
    "sesame": "sesame", "mustard": "mustard", "celery": "celery",
    "sulphites": "sulphites", "sulphur-dioxide": "sulphites",
    "lupin": "lupin", "molluscs": "molluscs",
}

def normalise_allergens(raw: str) -> list:
    if not isinstance(raw, str):
        return []
    tags = [t.strip().lower().replace("en:", "") for t in raw.split(",")]
    return list({ALLERGEN_NORMALISE[t] for t in tags if t in ALLERGEN_NORMALISE})

def run():
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    print("Loading Open Food Facts in chunks...")
    cols = ["product_name", "allergens_en", "traces_en"]
    rows = []
    chunk_size = 50_000
    total = 0

    for chunk in pd.read_csv(OFF_CSV, sep="\t", usecols=cols,
                              low_memory=False, on_bad_lines="skip",
                              chunksize=chunk_size):
        total += len(chunk)
        print(f"  Processed {total:,} rows...", end="\r")

        chunk = chunk.dropna(subset=["product_name"])
        for _, row in chunk.iterrows():
            name = str(row["product_name"]).strip()
            for col, relation in [("allergens_en", "HAS_ALLERGEN"),
                                   ("traces_en",    "MAY_CONTAIN_ALLERGEN")]:
                for allergen in normalise_allergens(row.get(col, "")):
                    rows.append({"subject": name, "relation": relation, "object": allergen})

    print(f"\n  Done. {total:,} products processed.")

    out_df = pd.DataFrame(rows).drop_duplicates()

    TRIPLE_ALLERGENS.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(TRIPLE_ALLERGENS, index=False)
    out_df.to_csv(DATA_PROC / "off_allergens.csv", index=False)

    print(f"  {len(out_df)} allergen triples")
    print(f"  -> {TRIPLE_ALLERGENS}")

if __name__ == "__main__":
    run()
