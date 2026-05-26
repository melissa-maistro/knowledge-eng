from graph.query import SubstitutionGraph
import json

sg = SubstitutionGraph()

print("=== RQ1: Substitutes for Butter (avoid: dairy) ===")
print(sg.substitutes("Butter", avoid_allergens=["dairy"]))

print("\n=== Butter neighbors (no filter) ===")
print(sg.substitutes("Butter", avoid_allergens=[]))

print("\n=== RQ2: Explain Butter <-> Avocado ===")
print(json.dumps(sg.explain("Butter", "Avocado"), indent=2))
