import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from graph.query import SubstitutionGraph
from config import TRIPLE_NUTRIENTS, DATA_PROC

# Map human-readable goals to USDA nutrient names
NUTRIENT_MAP = {
    "sodium": "Sodium, Na",
    "saturated_fat": "Fatty acids, total saturated",
    "sugar": "Sugars, total including NLEA",
    "calories": "Energy (Atwater General Factors)",
    "fat": "Total lipid (fat)",
    "carbs": "Carbohydrate, by difference",
}

class PatientConsultation(SubstitutionGraph):
    def __init__(self):
        super().__init__()
        self._load_nutrients()

    def _load_nutrients(self):
        print("Loading nutrient data...")
        if not TRIPLE_NUTRIENTS.exists():
            print("  WARNING: nutrients.csv not found")
            return
            
        # Map USDA descriptions to canonical names
        canon_df = pd.read_csv(DATA_PROC / "canonical_ingredients.csv")
        usda_to_canon = {}
        for _, row in canon_df.dropna(subset=["usda_description"]).iterrows():
            usda_to_canon[row["usda_description"]] = row["canonical_name"].strip()
            
        nut_df = pd.read_csv(TRIPLE_NUTRIENTS)
        nut_count = 0
        for _, row in nut_df.iterrows():
            usda_desc = row["subject"]
            if usda_desc in usda_to_canon:
                node = usda_to_canon[usda_desc]
                if node in self.G.nodes:
                    if "nutrients" not in self.G.nodes[node]:
                        self.G.nodes[node]["nutrients"] = {}
                    self.G.nodes[node]["nutrients"][row["relation_target"]] = float(row["amount"])
                    nut_count += 1
                    
        print(f"  Loaded {nut_count} nutrient values for canonical nodes.")

    def ask(self, ingredient: str, patient: dict, recipe_context: dict, top_n: int = 5):
        """
        Patient-facing query layer.
        patient = {"allergies": ["dairy"], "goals": {"reduce": ["saturated_fat", "sodium"]}}
        """
        avoid_allergens = patient.get("allergies", [])
        reduce_goals = patient.get("goals", {}).get("reduce", [])
        
        # 1. Get raw substitutes filtered strictly by allergies (unsafe to eat)
        # Using the parent class's substitutes method
        subs_df = self.substitutes(ingredient, avoid_allergens=avoid_allergens, top_n=top_n * 2)
        
        if subs_df.empty:
            return f"No safe substitutes found for '{ingredient}' given the allergies: {avoid_allergens}."
            
        # Try to find exactly the requested node to get base nutrients
        target_node = ingredient
        if ingredient not in self.G:
            matches = [n for n in self.G.nodes if n.lower() == ingredient.lower()]
            if matches:
                target_node = matches[0]
                
        target_nutrients = self.G.nodes.get(target_node, {}).get("nutrients", {})
        
        print(f"\n--- CONSULTATION CARD: Substituting {target_node} ---")
        print(f"Patient Allergies: {', '.join(avoid_allergens) if avoid_allergens else 'None'}")
        print(f"Patient Goals: Reduce {', '.join(reduce_goals) if reduce_goals else 'None'}")
        print(f"Recipe Context: {recipe_context.get('cuisine', 'Any')} cuisine, role: {recipe_context.get('role', 'Any')}")
        print("-" * 50)
        
        results_shown = 0
        for _, row in subs_df.iterrows():
            if results_shown >= top_n:
                break
                
            sub_node = row["substitute"]
            sub_nutrients = self.G.nodes.get(sub_node, {}).get("nutrients", {})
            
            # Formulate the reason string
            reason_parts = []
            
            # Flavor info
            shared = row["shared_molecules"]
            if shared > 0:
                reason_parts.append(f"{sub_node} shares {shared} flavour compounds with {target_node}.")
            else:
                reason_parts.append(f"{sub_node} acts as a culinary equivalent to {target_node}.")
                
            # Nutrient info
            warnings = []
            improvements = []
            
            for goal in reduce_goals:
                if goal in NUTRIENT_MAP:
                    nut_key = NUTRIENT_MAP[goal]
                    target_val = target_nutrients.get(nut_key)
                    sub_val = sub_nutrients.get(nut_key)
                    
                    if target_val is not None and sub_val is not None:
                        delta = target_val - sub_val
                        if delta > 0:
                            improvements.append(f"{goal.replace('_', ' ')} -{delta:.1f}g")
                        elif delta < 0:
                            warnings.append(f"Increases {goal.replace('_', ' ')} by {abs(delta):.1f}g")
                            
            if improvements:
                reason_parts.append(f"Nutritional improvement: {', '.join(improvements)} per 100g.")
            if warnings:
                reason_parts.append(f"⚠️ WARNING: {', '.join(warnings)} per 100g.")
                
            reason_parts.append("No allergens flagged.")
            
            consultation_string = " ".join(reason_parts)
            print(f"\nOption {results_shown + 1}: {sub_node} (Score: {row['score']:.2f})")
            print(f"  {consultation_string}")
            results_shown += 1
            
        print("-" * 50 + "\n")

    def get_consultation_data(self, ingredient: str, patient: dict, recipe_context: dict, top_n: int = 5):
        """
        Patient-facing query layer that returns structured data for the UI.
        """
        avoid_allergens = patient.get("allergies", [])
        reduce_goals = patient.get("goals", {}).get("reduce", [])
        
        subs_df = self.substitutes(ingredient, avoid_allergens=avoid_allergens, top_n=top_n * 2)
        
        if subs_df.empty:
            return {
                "success": False,
                "message": f"No safe substitutes found for '{ingredient}' given the allergies: {avoid_allergens}."
            }
            
        target_node = ingredient
        if ingredient not in self.G:
            matches = [n for n in self.G.nodes if n.lower() == ingredient.lower()]
            if matches:
                target_node = matches[0]
                
        target_nutrients = self.G.nodes.get(target_node, {}).get("nutrients", {})
        
        results = []
        for _, row in subs_df.iterrows():
            if len(results) >= top_n:
                break
                
            sub_node = row["substitute"]
            sub_nutrients = self.G.nodes.get(sub_node, {}).get("nutrients", {})
            
            shared = row["shared_molecules"]
            flavor_text = f"Shares {shared} flavour compounds with {target_node}." if shared > 0 else f"Acts as a culinary equivalent to {target_node}."
            
            warnings = []
            improvements = []
            
            for goal in reduce_goals:
                if goal in NUTRIENT_MAP:
                    nut_key = NUTRIENT_MAP[goal]
                    target_val = target_nutrients.get(nut_key)
                    sub_val = sub_nutrients.get(nut_key)
                    
                    if target_val is not None and sub_val is not None:
                        delta = target_val - sub_val
                        if delta > 0:
                            improvements.append(f"{goal.replace('_', ' ').capitalize()}: -{delta:.1f}g")
                        elif delta < 0:
                            warnings.append(f"Increases {goal.replace('_', ' ')} by {abs(delta):.1f}g")
                            
            results.append({
                "substitute": sub_node,
                "score": round(row["score"], 2),
                "flavor_text": flavor_text,
                "improvements": improvements,
                "warnings": warnings
            })
            
        return {
            "success": True,
            "target": target_node,
            "results": results
        }

if __name__ == "__main__":
    pc = PatientConsultation()
    
    # Test Priority 2 example from README
    pc.ask(
        ingredient="Butter",
        patient={"allergies": ["peanut"], "goals": {"reduce": ["saturated_fat", "sodium"]}},
        recipe_context={"cuisine": "italian", "role": "fat"}
    )
