# Summary of Project Updates (June 4, 2026)

This document provides a summary of the updates made to the Ingredient Substitution Knowledge Graph codebase to adjust similarity scoring and resolve functional classification issues.

---

## 1. Updated Similarity Weights
We adjusted the weights used to calculate the overall similarity score (`SIMILAR_TO` edges) in [graph/similarity.py](file:///Users/simone/Desktop/Uni/Knowledge%20Engineering/Group%20Project/knowledge-eng/graph/similarity.py) to give **Flavor (taste) Jaccard similarity** a non-zero impact.

### Weight Distribution Changes:
| Signal | Previous Weight | New Weight | Description |
|---|---|---|---|
| **Macro Similarity** | 0.90 (90%) | **0.85 (85%)** | Cosine similarity of macronutrient calorie profiles per 100g. |
| **Flavour Similarity** | 0.00 (0%) | **0.05 (5%)** | Jaccard similarity based on shared chemical flavor molecules. |
| **Nutrition Similarity** | 0.05 (5%) | 0.05 (5%) | Cosine similarity across full micronutrient profiles. |
| **Co-occurrence** | 0.05 (5%) | 0.05 (5%) | Recipe-based co-occurrence normalized frequency. |

---

## 2. Bug Fix in Functional Class Derivation
We resolved a critical logic error in [pipelines/normalise.py](file:///Users/simone/Desktop/Uni/Knowledge%20Engineering/Group%20Project/knowledge-eng/pipelines/normalise.py) that was causing almost all ingredients to get classified with a `functional_class = NaN`.

### Issue:
NumPy boolean addition performs a logical `OR` operation rather than arithmetic addition.
```python
# Before (Buggy NumPy logic):
nonzero = (row["fat_g"] > 0) + (row["prot_g"] > 0) + (row["carb_g"] > 0)
# Evaluated to True (which is 1) instead of 2 or 3.
# This caused the gate "if nonzero < 2" to always trigger, filtering out most ingredients.
```

### Fix:
Cast booleans to integers to ensure arithmetic sum computation:
```python
# After (Fixed):
nonzero = int(row["fat_g"] > 0) + int(row["prot_g"] > 0) + int(row["carb_g"] > 0)
```
This restored correct classifications for **carbs, proteins, and fats** sources across the entire canonical dataset.

---

## 3. Database Rebuild & Server Restart
- Regenerated the canonical list of ingredients using `pipelines/normalise.py`.
- Rebuilt recipe co-occurrence counts using `pipelines/foodcom.py`.
- Recomputed the similarity database using `graph/similarity.py` (generating 240 high-quality edges above the `0.15` threshold).
- Restarted the Dash server to reflect the updated graphs and weights.
