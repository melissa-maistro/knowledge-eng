"""
graph/query.py
In-memory query layer — answers the three core research questions.
No Neo4j needed; uses NetworkX loaded from the triple CSVs.

Usage:
    python graph/query.py
    
    or from another script:
    from graph.query import SubstitutionGraph
    sg = SubstitutionGraph()
    sg.substitutes("Butter", avoid_allergens=["dairy"])
"""
import sys
from pathlib import Path
import pandas as pd
import networkx as nx

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TRIPLE_SIMILARITY, TRIPLE_ALLERGENS, TRIPLE_NUTRIENTS, DATA_PROC


class SubstitutionGraph:
    def __init__(self):
        self.G = nx.Graph()
        self._load()

    def _load(self):
        print("Loading graph from triple files...")

        # ── Load canonical metadata and enrich graph nodes ────────────────────
        canonical_file = DATA_PROC / "canonical_ingredients.csv"
        self.canonical = None
        self._canon_df = None
        if canonical_file.exists():
            canon_df = pd.read_csv(canonical_file)
            self.canonical = set(canon_df["canonical_name"].str.strip())
            self._canon_df = canon_df
        else:
            print("  WARNING: canonical_ingredients.csv not found — loading all nodes")

        # ── Load SIMILAR_TO edges ─────────────────────────────────────────────
        if TRIPLE_SIMILARITY.exists():
            sim = pd.read_csv(TRIPLE_SIMILARITY)
            for _, r in sim.iterrows():
                self.G.add_edge(
                    r.ingredient_a, r.ingredient_b,
                    score=r.score, reason=r.reason,
                    flavour_score=r.flavour_score,
                    nutrition_score=r.get("nutrition_score", 0.0),
                    cooccurrence_score=r.get("cooccurrence_score", 0.0),
                    shared_molecules=int(r.shared_molecules),
                )

        # ── Attach node properties from canonical list ────────────────────────
        if self._canon_df is not None:
            for _, r in self._canon_df.iterrows():
                name = str(r["canonical_name"]).strip()
                if name in self.G:
                    self.G.nodes[name]["flavordb_category"] = r.get("flavordb_category", None)
                    self.G.nodes[name]["usda_category"] = r.get("usda_category", None)
                    self.G.nodes[name]["usda_description"] = r.get("usda_description", None)
                    self.G.nodes[name]["foodcom_count"] = r.get("foodcom_recipe_count", 0)
                    self.G.nodes[name]["functional_class"] = r.get("functional_class", None)

        # ── Load CONTAINS_ALLERGEN edges ──────────────────────────────────────
        if TRIPLE_ALLERGENS.exists():
            al = pd.read_csv(TRIPLE_ALLERGENS)
            if self.canonical:
                al = al[al["subject"].isin(self.canonical)]
            for _, r in al.iterrows():
                node = r["subject"]
                if node not in self.G:
                    self.G.add_node(node)
                allergens = self.G.nodes[node].get("allergens", set())
                allergens.add(r["object"])
                self.G.nodes[node]["allergens"] = allergens

        nodes_with_allergens = sum(1 for n in self.G.nodes if self.G.nodes[n].get("allergens"))
        print(f"  {self.G.number_of_nodes()} nodes | {self.G.number_of_edges()} edges loaded")
        print(f"  {nodes_with_allergens} nodes with allergen data\n")

    # ── RQ1: Safe substitutes under constraints ───────────────────────────────
    def substitutes(self, ingredient: str,
                    avoid_allergens: list = None,
                    top_n: int = 10) -> pd.DataFrame:
        """
        Find the best substitutes for `ingredient` that are safe for
        the given allergen constraints.

        Args:
            ingredient:       The ingredient to replace (must match node name)
            avoid_allergens:  List of allergen strings to exclude (e.g. ["dairy","gluten"])
            top_n:            How many results to return

        Returns:
            DataFrame with columns: substitute, score, shared_molecules, reason
        """
        avoid = set(a.lower() for a in (avoid_allergens or []))
        if ingredient not in self.G:
            # try case-insensitive match
            matches = [n for n in self.G.nodes if n.lower() == ingredient.lower()]
            if matches:
                ingredient = matches[0]
            else:
                print(f"  '{ingredient}' not found. Try: {self.search(ingredient[:4])[:5]}")
                return pd.DataFrame(columns=["substitute","score","shared_molecules","reason"])

        rows = []
        for neighbour, data in self.G[ingredient].items():
            node_allergens = self.G.nodes[neighbour].get("allergens", set())
            if avoid & node_allergens:
                continue
            rows.append({
                "substitute":       neighbour,
                "score":            data.get("score", 0),
                "shared_molecules": data.get("shared_molecules", 0),
                "reason":           data.get("reason", ""),
            })

        if not rows:
            return pd.DataFrame(columns=["substitute","score","shared_molecules","reason"])

        return (pd.DataFrame(rows)
                  .sort_values("score", ascending=False)
                  .head(top_n)
                  .reset_index(drop=True))

    # ── RQ2: Explain similarity between two ingredients ───────────────────────
    def explain(self, a: str, b: str) -> dict:
        """
        Return human-readable evidence behind a specific ingredient pair.
        This is the traceable justification the dietitian can show the patient.
        """
        # case-insensitive fallback
        for name in [a, b]:
            if name not in self.G:
                matches = [n for n in self.G.nodes if n.lower() == name.lower()]
                if matches:
                    a, b = (matches[0] if name == a else a), (matches[0] if name == b else b)

        if not self.G.has_edge(a, b):
            return {"found": False, "message": f"No similarity edge between '{a}' and '{b}'"}

        data = dict(self.G[a][b])
        fl = data.get("flavour_score", 0)
        nt = data.get("nutrition_score", 0)
        mc = data.get("macro_score", 0)
        co = data.get("cooccurrence_score", 0)
        shared = data.get("shared_molecules", 0)
        score = data.get("score", 0)

        explanation = {
            "found": True,
            "pair": (a, b),
            "overall_score": round(score, 3),
            "signals": {
                "flavour": {
                    "score": round(fl, 3),
                    "shared_molecules": shared,
                    "interpretation": f"{a} and {b} share {shared} flavour molecules (Jaccard={fl:.2f})",
                },
                "nutrition": {
                    "score": round(nt, 3),
                    "interpretation": (
                        f"Nutritional profiles are {'very similar' if nt > 0.8 else 'moderately similar' if nt > 0.5 else 'somewhat different'} (cosine={nt:.2f})"
                        if nt > 0 else "No full nutritional data available for this pair"
                    ),
                },
                "macro": {
                    "score": round(mc, 3),
                    "interpretation": (
                        f"Macro balance (protein/fat/carb) is {'very similar' if mc > 0.8 else 'moderately similar' if mc > 0.5 else 'somewhat different'} (cosine={mc:.2f})"
                        if mc > 0 else "No macro data available for this pair"
                    ),
                },
                "cooccurrence": {
                    "score": round(co, 3),
                    "interpretation": (
                        f"These ingredients are frequently used together in recipes (co-occurrence={co:.2f})"
                        if co > 0 else "No co-occurrence data available"
                    ),
                },
            },
            "summary": (
                f"{a} and {b} have an overall similarity score of {score:.2f}. "
                f"They share {shared} flavour molecules. "
                + (f"Nutritional profiles are cosine-similar at {nt:.2f}. " if nt > 0 else "")
                + (f"Macro balance is cosine-similar at {mc:.2f}. " if mc > 0 else "")
                + (f"Co-occur in recipes at {co:.2f}. " if co > 0 else "")
            ),
        }
        return explanation

    # ── RQ3: Cuisine-filtered substitutes ─────────────────────────────────────
    def substitutes_in_cuisine(self, ingredient: str, cuisine: str,
                                avoid_allergens: list = None,
                                top_n: int = 10) -> pd.DataFrame:
        """
        Filter substitutes by the FlavorDB category of the ingredient
        (as a proxy for culinary role / cuisine fit).
        Ingredients with higher Food.com recipe counts are ranked higher.
        When foodcom_cuisines.csv is available it will be used instead.
        """
        cuisine_path = DATA_PROC / "foodcom_cuisines.csv"

        # ── Full cuisine filter when ingredient-level cuisine data is available ─
        if cuisine_path.exists():
            cuisine_df = pd.read_csv(cuisine_path)
            if "canonical_name" in cuisine_df.columns:
                cuisine_ingredients = set(
                    cuisine_df[cuisine_df["cuisine"].str.lower() == cuisine.lower()]["canonical_name"]
                )
                subs = self.substitutes(ingredient, avoid_allergens, top_n * 3)
                subs = subs[subs["substitute"].isin(cuisine_ingredients)]
                return subs.head(top_n)
            # foodcom_cuisines.csv is recipe-level (no canonical_name) — fall through

        # ── Fallback: use FlavorDB category + Food.com recipe count ───────────
        subs = self.substitutes(ingredient, avoid_allergens, top_n * 3)
        if subs.empty:
            return subs

        # boost by recipe count as a proxy for "how common is this in recipes"
        subs["foodcom_count"] = subs["substitute"].apply(
            lambda n: self.G.nodes[n].get("foodcom_count", 0) or 0
        )
        # normalise count to 0-1 and add a 10% boost to score
        max_count = subs["foodcom_count"].max()
        if max_count > 0:
            subs["score"] = (
                subs["score"] + 0.10 * (subs["foodcom_count"] / max_count)
            ).clip(upper=1.0)

        return (subs.sort_values("score", ascending=False)
                    .drop(columns=["foodcom_count"])
                    .head(top_n)
                    .reset_index(drop=True))

    # ── Utility ───────────────────────────────────────────────────────────────
    def search(self, keyword: str) -> list:
        kw = keyword.lower()
        nodes = self.canonical if self.canonical else self.G.nodes
        return [n for n in nodes if kw in n.lower()]

    def stats(self):
        print(f"Nodes    : {self.G.number_of_nodes()}")
        print(f"Edges    : {self.G.number_of_edges()}")
        allergen_nodes = sum(1 for n in self.G.nodes
                             if self.G.nodes[n].get("allergens"))
        print(f"With allergen data: {allergen_nodes}")


# ── Test all 3 Research Questions ─────────────────────────────────────────────
if __name__ == "__main__":
    import json
    sg = SubstitutionGraph()
    sg.stats()

    print("\n═══════════════════════════════════════════════════")
    print("RQ1: Safe substitutes under constraints")
    print("═══════════════════════════════════════════════════")
    print("\n── Substitutes for 'Butter' (avoid: dairy) ──")
    print(sg.substitutes("Butter", avoid_allergens=["dairy"]))

    print("\n── Substitutes for 'Wheat' (avoid: gluten) ──")
    print(sg.substitutes("Wheat", avoid_allergens=["gluten"]))

    print("\n═══════════════════════════════════════════════════")
    print("RQ2: What makes two ingredients similar?")
    print("═══════════════════════════════════════════════════")
    print("\n── Explain Rye <-> Wheat ──")
    result = sg.explain("Rye", "Wheat")
    print(json.dumps(result, indent=2))

    print("\n═══════════════════════════════════════════════════")
    print("RQ3: Cuisine-aware substitutes")
    print("═══════════════════════════════════════════════════")
    print("\n── Substitutes for 'Wheat' in 'italian' context (avoid: gluten) ──")
    print(sg.substitutes_in_cuisine("Wheat", cuisine="italian", avoid_allergens=["gluten"]))
