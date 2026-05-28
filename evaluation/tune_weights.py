"""
evaluation/tune_weights.py
Grid search over scoring weights using the gold standard.

The raw per-signal scores are already stored in similarity.csv so we can
re-weight without re-running the full pipeline.

Metrics:
  MRR  — Mean Reciprocal Rank (higher = better)
  H@5  — Hit@5: fraction of gold pairs where substitute ranks in top 5
  H@10 — Hit@10: fraction of gold pairs where substitute ranks in top 10

Usage:
    python evaluation/tune_weights.py
    python evaluation/tune_weights.py --top 20
"""
import sys, argparse
from pathlib import Path
from itertools import product

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TRIPLE_SIMILARITY

GOLD_FILE = Path(__file__).parent / "gold_standard.csv"


def load_sim() -> pd.DataFrame:
    sim = pd.read_csv(TRIPLE_SIMILARITY)
    for col in ["flavour_score", "nutrition_score", "macro_score", "cooccurrence_score"]:
        if col not in sim.columns:
            sim[col] = 0.0
    return sim


def get_neighbors(sim: pd.DataFrame, ingredient: str, weights: tuple) -> pd.Series:
    """Return substitutes for ingredient ranked by the given weights."""
    wf, wn, wm, wc = weights
    mask = (sim["ingredient_a"] == ingredient) | (sim["ingredient_b"] == ingredient)
    rows = sim[mask].copy()
    if rows.empty:
        return pd.Series(dtype=float)

    rows["substitute"] = rows.apply(
        lambda r: r["ingredient_b"] if r["ingredient_a"] == ingredient else r["ingredient_a"],
        axis=1,
    )
    rows["weighted_score"] = (
        wf * rows["flavour_score"] +
        wn * rows["nutrition_score"] +
        wm * rows["macro_score"] +
        wc * rows["cooccurrence_score"]
    )
    return rows.set_index("substitute")["weighted_score"].sort_values(ascending=False)


def evaluate(sim: pd.DataFrame, gold: pd.DataFrame, weights: tuple) -> dict:
    reciprocal_ranks = []
    hits5 = []
    hits10 = []

    for _, row in gold.iterrows():
        ing, sub = row["ingredient"], row["substitute"]
        ranked = get_neighbors(sim, ing, weights)
        if ranked.empty or sub not in ranked.index:
            reciprocal_ranks.append(0.0)
            hits5.append(0)
            hits10.append(0)
            continue
        rank = ranked.index.tolist().index(sub) + 1  # 1-based
        reciprocal_ranks.append(1.0 / rank)
        hits5.append(1 if rank <= 5 else 0)
        hits10.append(1 if rank <= 10 else 0)

    return {
        "MRR":  round(np.mean(reciprocal_ranks), 4),
        "H@5":  round(np.mean(hits5), 4),
        "H@10": round(np.mean(hits10), 4),
    }


def grid_search(sim: pd.DataFrame, gold: pd.DataFrame, step: float = 0.05) -> pd.DataFrame:
    vals = np.arange(0, 1 + step, step).round(2)
    results = []

    total = sum(1 for wf, wn, wm, wc in product(vals, repeat=4)
                if abs(wf + wn + wm + wc - 1.0) < 1e-6)
    print(f"Evaluating {total:,} weight combinations (step={step})...")

    for wf, wn, wm, wc in product(vals, repeat=4):
        if abs(wf + wn + wm + wc - 1.0) > 1e-6:
            continue
        weights = (wf, wn, wm, wc)
        metrics = evaluate(sim, gold, weights)
        results.append({
            "w_flavour":     wf,
            "w_nutrition":   wn,
            "w_macro":       wm,
            "w_cooccurrence": wc,
            **metrics,
        })

    return pd.DataFrame(results).sort_values(["MRR", "H@5", "H@10"], ascending=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=10, help="Number of top results to show")
    parser.add_argument("--step", type=float, default=0.05, help="Grid step size (default 0.05)")
    args = parser.parse_args()

    print("Loading similarity data...")
    sim = load_sim()
    gold = pd.read_csv(GOLD_FILE)
    print(f"Gold standard: {len(gold)} pairs")

    # Baseline: current weights (tuned via grid search 2026-05-28)
    current = (0.00, 0.05, 0.90, 0.05)
    baseline = evaluate(sim, gold, current)
    print(f"\nCurrent weights (f={current[0]}, n={current[1]}, m={current[2]}, c={current[3]}):")
    print(f"  MRR={baseline['MRR']:.4f}  H@5={baseline['H@5']:.4f}  H@10={baseline['H@10']:.4f}")

    print()
    results = grid_search(sim, gold, step=args.step)

    print(f"\nTop {args.top} weight combinations:")
    print(results.head(args.top).to_string(index=False))

    out = Path(__file__).parent / "weight_search_results.csv"
    results.to_csv(out, index=False)
    print(f"\nFull results saved to {out}")

    best = results.iloc[0]
    print(f"\nBest weights:")
    print(f"  flavour={best.w_flavour}  nutrition={best.w_nutrition}  "
          f"macro={best.w_macro}  cooccurrence={best.w_cooccurrence}")
    print(f"  MRR={best['MRR']:.4f}  H@5={best['H@5']:.4f}  H@10={best['H@10']:.4f}")


if __name__ == "__main__":
    main()
