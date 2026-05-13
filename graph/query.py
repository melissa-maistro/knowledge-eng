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

        # load canonical names to filter nodes
        canonical_file = DATA_PROC / "canonical_ingredients.csv"
        if canonical_file.exists():
            canon_df = pd.read_csv(canonical_file)
            self.canonical = set(canon_df["canonical_name"].str.strip())
        else:
            self.canonical = None
            print("  WARNING: canonical_ingredients.csv not found — loading all nodes")

        if TRIPLE_SIMILARITY.exists():
            sim = pd.read_csv(TRIPLE_SIMILARITY)
            for _, r in sim.iterrows():
                self.G.add_edge(
                    r.ingredient_a, r.ingredient_b,
                    score=r.score, reason=r.reason,
                    flavour_score=r.flavour_score,
                    shared_molecules=int(r.shared_molecules),
                )

        # only load allergens for canonical ingredients
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

        print(f"  {self.G.number_of_nodes()} nodes | {self.G.number_of_edges()} edges loaded\n")

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

        return (pd.DataFrame(rows)
                  .sort_values("score", ascending=False)
                  .head(top_n)
                  .reset_index(drop=True))

    # ── RQ2: Explain similarity between two ingredients ───────────────────────
    def explain(self, a: str, b: str) -> dict:
        """
        Return the evidence behind a specific ingredient pair.
        This is the "traceable reason" for the dietitian to show the patient.
        """
        if not self.G.has_edge(a, b):
            return {"message": f"No similarity edge between '{a}' and '{b}'"}
        data = dict(self.G[a][b])
        data["pair"] = (a, b)
        return data

    # ── RQ3: Cuisine-filtered substitutes ─────────────────────────────────────
    def substitutes_in_cuisine(self, ingredient: str, cuisine: str,
                                avoid_allergens: list = None,
                                top_n: int = 10) -> pd.DataFrame:
        """
        Filter substitutes to those that co-occur with foods from a given cuisine.
        Requires foodcom_cuisines.csv to be present.
        """
        from config import DATA_PROC
        cuisine_path = DATA_PROC / "foodcom_cuisines.csv"
        if not cuisine_path.exists():
            print("  foodcom_cuisines.csv not found — run pipelines/foodcom.py first")
            return self.substitutes(ingredient, avoid_allergens, top_n)

        # get ingredients that appear in recipes tagged with this cuisine
        # (stub: in production, join via cooccurrence on recipe id)
        subs = self.substitutes(ingredient, avoid_allergens, top_n * 3)
        # TODO: filter to cuisine-appropriate candidates
        return subs.head(top_n)

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


# ── Example queries ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    sg = SubstitutionGraph()
    sg.stats()

    print("\n── Substitutes for 'Butter' (avoid: dairy) ──")
    print(sg.substitutes("Butter", avoid_allergens=["dairy"]))

    print("\n── Substitutes for 'Wheat' (avoid: gluten) ──")
    print(sg.substitutes("Wheat", avoid_allergens=["gluten"]))

    print("\n── Explain Butter <-> Olive oil ──")
    print(sg.explain("Butter", "Olive oil"))

    print("\n── Search 'garlic' ──")
    print(sg.search("garlic"))
