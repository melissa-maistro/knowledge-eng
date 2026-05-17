"""
pipelines/foodcom.py
Extracts ingredient co-occurrence and cuisine tags from Food.com recipes.

Download first (requires free Kaggle account):
  https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions
  -> RAW_recipes.csv -> place in data/raw/
"""
import sys, ast
from pathlib import Path
from collections import Counter
from itertools import combinations
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import FOODCOM_RECIPES, DATA_PROC, TRIPLE_COOCCURRENCE

MIN_COOCCURRENCE = 10   # ignore pairs appearing together fewer than this many times

CUISINE_TAGS = {
    "italian","mexican","indian","chinese","japanese","french","thai",
    "mediterranean","american","greek","spanish","korean","vietnamese",
    "middle-eastern","british","german","caribbean","african","moroccan",
}

def parse_list(raw) -> list:
    try:
        return ast.literal_eval(raw) if isinstance(raw, str) else []
    except Exception:
        return []

def get_cuisine(tags: list) -> str:
    for t in tags:
        if t in CUISINE_TAGS:
            return t
    return "unknown"

def run():
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    print("Loading Food.com recipes...")
    df = pd.read_csv(FOODCOM_RECIPES, usecols=["id","name","ingredients","tags"])
    df["ingredients_parsed"] = df["ingredients"].apply(parse_list)
    df["tags_parsed"]        = df["tags"].apply(parse_list)
    df["cuisine"]            = df["tags_parsed"].apply(get_cuisine)

    # ── cuisine labels ────────────────────────────────────────────────────────
    cuisine_out = DATA_PROC / "foodcom_cuisines.csv"
    df[["id","name","cuisine"]].to_csv(cuisine_out, index=False)

    # ── co-occurrence counts ──────────────────────────────────────────────────
    print("Computing co-occurrence pairs (may take a few minutes)...")
    counter = Counter()
    for ingredients in df["ingredients_parsed"]:
        cleaned = [i.lower().strip() for i in ingredients]
        for a, b in combinations(sorted(set(cleaned)), 2):
            counter[(a, b)] += 1

    pairs = [
        {"ingredient_a": a, "ingredient_b": b, "cooccurrence_count": n}
        for (a, b), n in counter.items()
        if n >= MIN_COOCCURRENCE
    ]
    pairs_df = pd.DataFrame(pairs).sort_values("cooccurrence_count", ascending=False)

    TRIPLE_COOCCURRENCE.parent.mkdir(parents=True, exist_ok=True)
    pairs_df.to_csv(TRIPLE_COOCCURRENCE, index=False)
    pairs_df.to_csv(DATA_PROC / "foodcom_cooccurrence.csv", index=False)

    print(f"  {len(df)} recipes | {len(pairs_df)} co-occurrence pairs (min {MIN_COOCCURRENCE})")
    print(f"  -> {cuisine_out}")
    print(f"  -> {TRIPLE_COOCCURRENCE}")

if __name__ == "__main__":
    run()
