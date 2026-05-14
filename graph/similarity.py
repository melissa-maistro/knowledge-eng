"""
graph/similarity.py
Computes SIMILAR_TO edges from canonical ingredients only.
Filters out OFF packaged products — only whole ingredients from FlavorDB
are used as nodes.

Run after pipelines/normalise.py has completed.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import normalize
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (FLAVORDB_LINKS_CSV, TRIPLE_NUTRIENTS,
                    TRIPLE_COOCCURRENCE, TRIPLE_SIMILARITY, DATA_PROC)

W_FLAVOUR       = 0.50
W_NUTRITION     = 0.30
W_COOCCURRENCE  = 0.20
MIN_SCORE       = 0.15

CANONICAL_FILE  = DATA_PROC / "canonical_ingredients.csv"


def load_canonical_names() -> set:
    if not CANONICAL_FILE.exists():
        print("  WARNING: canonical_ingredients.csv not found.")
        print("  Run pipelines/normalise.py first for best results.")
        print("  Falling back to all FlavorDB entities...")
        flavordb = pd.read_csv(DATA_PROC / "flavordb_entities.csv")
        return set(flavordb["entity_alias_readable"].str.strip())
    df = pd.read_csv(CANONICAL_FILE)
    names = set(df["canonical_name"].str.strip())
    print(f"  Loaded {len(names)} canonical ingredient names")
    return names


def flavour_similarity(canonical_names: set) -> pd.DataFrame:
    links = pd.read_csv(FLAVORDB_LINKS_CSV)
    links = links[links["entity_name"].isin(canonical_names)]
    grouped = links.groupby("entity_name")["pubchem_id"].apply(set).to_dict()
    ingredients = list(grouped.keys())
    rows = []
    for i, a in enumerate(ingredients):
        for b in ingredients[i+1:]:
            s_a, s_b = grouped[a], grouped[b]
            shared = s_a & s_b
            if not shared:
                continue
            score = len(shared) / len(s_a | s_b)
            rows.append({
                "ingredient_a": a, "ingredient_b": b,
                "flavour_score": round(score, 4),
                "shared_molecules": len(shared),
            })
    print(f"  {len(rows)} flavour pairs from {len(ingredients)} ingredients")
    return pd.DataFrame(rows)


def nutrition_similarity(canonical_names: set, top_n=10000) -> pd.DataFrame:
    if not TRIPLE_NUTRIENTS.exists():
        print("  Nutrients file not found — skipping nutrition similarity")
        return pd.DataFrame(columns=["ingredient_a","ingredient_b","nutrition_score"])

    nt = pd.read_csv(TRIPLE_NUTRIENTS)

    if CANONICAL_FILE.exists():
        canon = pd.read_csv(CANONICAL_FILE)[["canonical_name","usda_description"]].dropna()
        desc_to_canon = dict(zip(canon["usda_description"], canon["canonical_name"]))
        nt["subject"] = nt["subject"].map(desc_to_canon).fillna(nt["subject"])

    nt = nt[nt["subject"].isin(canonical_names)]

    if nt.empty:
        print("  No canonical ingredients matched in USDA data")
        return pd.DataFrame(columns=["ingredient_a","ingredient_b","nutrition_score"])

    pivot = nt.pivot_table(index="subject", columns="relation_target",
                           values="amount", aggfunc="mean").fillna(0)
    matrix = normalize(pivot.values)
    sim = cosine_similarity(matrix)
    names = pivot.index.tolist()
    rows = []
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            s = float(sim[i, j])
            if s > 0.5:
                rows.append({
                    "ingredient_a": names[i], "ingredient_b": names[j],
                    "nutrition_score": round(s, 4)
                })
    df = pd.DataFrame(rows).sort_values("nutrition_score", ascending=False).head(top_n)
    print(f"  {len(df)} nutrition pairs")
    return df


def cooccurrence_similarity(canonical_names: set) -> pd.DataFrame:
    if not TRIPLE_COOCCURRENCE.exists():
        print("  Co-occurrence file not found — skipping")
        return pd.DataFrame(columns=["ingredient_a","ingredient_b","cooccurrence_score"])

    df = pd.read_csv(TRIPLE_COOCCURRENCE)
    df = df[
        df["ingredient_a"].isin(canonical_names) &
        df["ingredient_b"].isin(canonical_names)
    ]

    if df.empty:
        print("  No canonical pairs in co-occurrence data")
        print("  (Food.com strings may need normalisation — run pipelines/normalise.py)")
        return pd.DataFrame(columns=["ingredient_a","ingredient_b","cooccurrence_score"])

    max_count = df["cooccurrence_count"].max()
    df["cooccurrence_score"] = (df["cooccurrence_count"] / max_count).round(4)
    print(f"  {len(df)} co-occurrence pairs")
    return df[["ingredient_a","ingredient_b","cooccurrence_score"]]


def canonical_pair(a, b):
    return tuple(sorted([str(a), str(b)]))


def run():
    print("Loading canonical ingredient list...")
    canonical_names = load_canonical_names()

    print("\nComputing flavour similarity...")
    fl = flavour_similarity(canonical_names)
    fl["pair"] = fl.apply(lambda r: canonical_pair(r.ingredient_a, r.ingredient_b), axis=1)

    print("\nComputing nutritional similarity...")
    nt = nutrition_similarity(canonical_names)
    nt["pair"] = nt.apply(lambda r: canonical_pair(r.ingredient_a, r.ingredient_b), axis=1)

    print("\nLoading co-occurrence...")
    co = cooccurrence_similarity(canonical_names)
    co["pair"] = co.apply(lambda r: canonical_pair(r.ingredient_a, r.ingredient_b), axis=1)

    print("\nCombining signals...")
    merged = fl.merge(nt[["pair","nutrition_score"]], on="pair", how="outer")
    merged = merged.merge(co[["pair","cooccurrence_score"]], on="pair", how="outer")

    for col in ["flavour_score","nutrition_score","cooccurrence_score"]:
        merged[col] = merged.get(col, 0).fillna(0.0)
    merged["shared_molecules"] = merged.get("shared_molecules", 0).fillna(0).astype(int)

    merged["ingredient_a"] = merged["pair"].apply(lambda p: p[0])
    merged["ingredient_b"] = merged["pair"].apply(lambda p: p[1])

    print("Applying strict category filter...")
    if CANONICAL_FILE.exists():
        canon = pd.read_csv(CANONICAL_FILE)
        usda_cat = dict(zip(canon["canonical_name"], canon["usda_category"]))
        fdb_cat  = dict(zip(canon["canonical_name"], canon["flavordb_category"]))

        def category_match(a, b):
            u_a, u_b = usda_cat.get(a), usda_cat.get(b)
            f_a, f_b = fdb_cat.get(a), fdb_cat.get(b)

            # 1. Strict USDA Category Match (if both are known)
            if pd.notna(u_a) and pd.notna(u_b) and u_a != "Unknown" and u_b != "Unknown":
                return u_a == u_b
            
            # 2. Fallback to FlavorDB Category Match
            if pd.notna(f_a) and pd.notna(f_b):
                return f_a == f_b
                
            return False

        merged["valid_category"] = merged.apply(lambda r: category_match(r.ingredient_a, r.ingredient_b), axis=1)
        before_count = len(merged)
        merged = merged[merged["valid_category"]].copy()
        print(f"  Filtered out {before_count - len(merged)} pairs due to category mismatch.")
    else:
        print("  WARNING: canonical_ingredients.csv not found, skipping category filter.")

    merged["score"] = (
        W_FLAVOUR      * merged["flavour_score"] +
        W_NUTRITION    * merged["nutrition_score"] +
        W_COOCCURRENCE * merged["cooccurrence_score"]
    ).round(4)

    merged["reason"] = merged.apply(lambda r:
        f"Flavour:{r['flavour_score']:.2f} ({r['shared_molecules']} shared molecules); "
        f"Nutrition:{r['nutrition_score']:.2f}; "
        f"Co-occurrence:{r['cooccurrence_score']:.2f}", axis=1)

    out = merged[merged["score"] >= MIN_SCORE][
        ["ingredient_a","ingredient_b","score",
         "flavour_score","nutrition_score","cooccurrence_score",
         "shared_molecules","reason"]
    ].sort_values("score", ascending=False).reset_index(drop=True)

    TRIPLE_SIMILARITY.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(TRIPLE_SIMILARITY, index=False)

    print(f"\n  {len(out)} similarity edges (score >= {MIN_SCORE})")
    print(f"  -> {TRIPLE_SIMILARITY}")
    print(f"\nTop 5 most similar pairs:")
    print(out[["ingredient_a","ingredient_b","score","shared_molecules"]].head().to_string(index=False))

if __name__ == "__main__":
    run()
