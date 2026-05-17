# Recipe Substitution Knowledge Graph
**Group 3 — Knowledge Engineering Project**
Client: Dietetics clinic (outpatient / community)

---

## What this project does

We are building a knowledge graph that answers the question:
*"When a patient needs to remove or reduce an ingredient from a home-cooked recipe, what can they safely substitute it with — given their allergies, nutritional goals, and the dish they are cooking?"*

The graph combines four public datasets to produce a scored, traceable substitution suggestion for each ingredient query.

---

## Project structure

```
recipe_substitution/
├── config.py                   ← all file paths in one place — edit this if you move data
├── requirements.txt
├── data/
│   ├── raw/                    ← original downloads, never modify these
│   │   ├── flavordb_entities.csv, flavordb_molecules.csv, flavordb_links.csv
│   │   ├── food.csv, nutrient.csv, food_nutrient.csv, food_category.csv
│   │   ├── en.openfoodfacts.org.products.csv.gz
│   │   └── RAW_recipes.csv
│   ├── processed/              ← cleaned outputs from each pipeline
│   │   ├── flavordb_entities.csv
│   │   ├── flavordb_molecules.csv
│   │   ├── flavordb_links.csv
│   │   ├── usda_ingredients.csv        ← deduplicated USDA ingredients with categories
│   │   ├── usda_nutrients.csv
│   │   ├── off_allergens.csv
│   │   ├── foodcom_cooccurrence.csv
│   │   ├── foodcom_cuisines.csv
│   │   └── canonical_ingredients.csv   ← the key integration file
│   └── triples/                ← graph-ready edge files
│       ├── nutrients.csv
│       ├── allergens.csv
│       ├── cooccurrence.csv
│       └── similarity.csv      ← the core of the graph, computed last
├── pipelines/
│   ├── flavordb.py             ← copies pre-scraped FlavorDB files into place
│   ├── usda.py                 ← extracts nutrients from USDA Foundation Foods
│   ├── openfoodfacts.py        ← extracts allergen data from Open Food Facts
│   ├── foodcom.py              ← extracts co-occurrence and cuisine from Food.com
│   └── normalise.py            ← builds canonical ingredient list, links all sources
├── graph/
│   ├── similarity.py           ← computes SIMILAR_TO edges (run after all pipelines)
│   ├── query.py                ← in-memory query layer, test substitution suggestions
│   └── load.py                 ← optional: bulk import into Neo4j
└── notebooks/                  ← optional
```

---

## Data sources

| Source | What we use it for | Size | License |
|--------|-------------------|------|---------|
| **FlavorDB2** (IIIT Delhi) | Flavour molecule links between ~936 whole ingredients | ~1 MB | CC BY-NC-SA 3.0 |
| **USDA FoodData Central** | Nutrient values per 100g for Foundation Foods | ~50 MB | CC0 |
| **Open Food Facts** | Allergen and intolerance tags on packaged products | ~9 GB | ODbL |
| **Food.com** (Kaggle) | Ingredient co-occurrence and cuisine tags from 230k recipes | ~200 MB | Kaggle |

FlavorDB was scraped using a separate script (`flavordb_scrape.py`, not in this repo). The three output CSVs should be placed in `data/raw/`.

---

## How the datasets are integrated

All four sources are linked through a **canonical ingredient list** (`data/processed/canonical_ingredients.csv`). This file has one row per whole ingredient (~935 ingredients from FlavorDB) and maps each one to its equivalent entry in USDA, Open Food Facts, and Food.com.

The integration works as follows:

1. **FlavorDB** provides the canonical ingredient names — 936 whole foods across 34 categories. These are the nodes of the graph.
2. **USDA** is matched to canonical names by fuzzy-matching ingredient names against USDA Foundation Foods descriptions (root name before the first comma). 304/935 matched with high confidence.
3. **Open Food Facts** allergen tags are normalised to a fixed vocabulary (gluten, dairy, eggs, tree_nuts, peanuts, soy, fish, shellfish, sesame, sulphites) and attached to matching canonical nodes.
4. **Food.com** recipe strings are searched for canonical ingredient names to count co-occurrence frequency across 230k recipes.

---

## How similarity is computed

The `graph/similarity.py` script computes a `SIMILAR_TO` edge between ingredient pairs using three signals:

| Signal | Source | Weight | How |
|--------|--------|--------|-----|
| Flavour similarity | FlavorDB | 0.50 | Jaccard on shared flavour molecules |
| Nutritional proximity | USDA | 0.30 | Cosine similarity on nutrient vectors |
| Co-occurrence | Food.com | 0.20 | Normalised co-occurrence count |

Only edges scoring ≥ 0.15 are kept. The graph currently has **117,018 similarity edges** across **935 ingredients**.

---

## Current status

### What works
- All four pipelines run end to end
- Canonical ingredient list built with 304 USDA matches and 935 Food.com appearance counts
- 117,018 similarity edges computed
- Allergen filter working — dairy ingredients correctly excluded from butter substitutes
- Query layer filters to canonical whole ingredients only (no packaged products in results)

### Known limitations

1. **No Butter ↔ Olive oil edge.** FlavorDB shows they share almost no flavour molecules. The flavour signal dominates (weight 0.50) but does not capture culinary function. Olive oil and butter are both fats but have very different volatile compound profiles.
2. **USDA coverage is currently at 304/935 (32%).** (Improved from 99/935). Foundation Foods only provides 401 unique ingredients. SR Legacy would increase coverage but contains branded foods that corrupt fuzzy matching.
3. **Food.com co-occurrence is zero.** Food.com ingredient strings ("2 cups all-purpose flour") don't match canonical names ("Flour") exactly enough to produce co-occurrence pairs. Needs a normalisation pass on Food.com strings.
4. **Open Food Facts allergen coverage is for packaged products only.** Whole ingredients like butter, olive oil, garlic have no OFF entries — allergen data for these needs to be added separately.

---

## Recent Pipeline Improvements

To support better reporting and data quality, several enhancements were recently made to the preprocessing pipelines:

1. **USDA Deduplication & Aggregation:** The raw USDA Foundation Foods database contained multiple samples (FDC IDs) for the exact same ingredient description (e.g., different expiration dates). `usda.py` now groups identical descriptions and computes the arithmetic mean for all macronutrients. This reduced 469 raw entries to **401 unique, clean ingredients**, eliminating duplicates in the graph.
2. **USDA Categories:** We integrated `food_category.csv` into `usda.py`, which now outputs `usda_ingredients.csv` containing the `category` for each ingredient. `normalise.py` was updated to carry this category into the canonical ingredient list.
3. **Improved Matching Strategy:** By introducing a fuzzy matching strategy (using `fuzz.WRatio`) and un-inverting strings (e.g., converting "Oil, olive" to "olive oil"), the matching accuracy between FlavorDB and USDA Foundation Foods skyrocketed. 
   - **Before:** 99 / 935 matches (11% coverage)
   - **After:** 304 / 935 matches (32% coverage)
4. **Simplified Paths:** Directory structures for raw downloads were flattened. Files can now be dropped directly into `data/raw/` without subfolders.

---

## What needs to be done next

### Priority 1 — Culinary role layer (COMPLETED)
The culinary role problem (e.g., Zucchini vs Wheat) has been resolved. `graph/similarity.py` now enforces a **strict category filter**. 
Pairs are only preserved if their `usda_category` matches (or `flavordb_category` as fallback). This eliminated ~336k nonsensical cross-category edges, ensuring a carb substitutes a carb, and a vegetable substitutes a vegetable.

### Priority 2 — Patient-facing query layer
Build `graph/substitution.py` with a proper patient profile:
```python
ask(
    ingredient="Butter",
    patient={"allergies": ["dairy"], "goals": {"reduce": ["saturated_fat", "sodium"]}},
    recipe_context={"cuisine": "italian", "role": "fat"}
)
```
Output should be a consultation card with a human-readable reason string:
*"Olive oil shares 4 flavour compounds with Butter. Nutritional improvement for your goal: saturated fat −23g per 100g. No allergens flagged."*

### Priority 3 — Cuisine-aware filter
Build `graph/cuisine.py` that filters substitutes to those that appear in recipes tagged with the same cuisine as the original dish. Requires fixing Food.com co-occurrence matching first.

### Priority 4 — Improve USDA coverage
Either download SR Legacy separately and clean it, or supplement Foundation Foods with a small curated nutrient table for the most common unmatched ingredients (Butter, Salt, Pepper etc.).

---

## Setup

```bash
pip install -r requirements.txt
```

### Run order
```bash
python pipelines/flavordb.py        # copies FlavorDB files into place
python pipelines/usda.py            # requires USDA download
python pipelines/openfoodfacts.py   # requires OFF download, ~20 min
python pipelines/foodcom.py         # requires Kaggle download
python pipelines/normalise.py       # builds canonical ingredient list
python graph/similarity.py          # computes SIMILAR_TO edges
python graph/query.py               # test queries
```

### Data downloads required

| File | Where | Place in |
|------|-------|----------|
| USDA Foundation Foods ZIP | https://fdc.nal.usda.gov/download-datasets | `data/raw/` |
| Open Food Facts CSV | https://world.openfoodfacts.org/data | `data/raw/` |
| Food.com RAW_recipes.csv | https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions | `data/raw/` |

FlavorDB CSVs should already be in `data/raw/`.

---

## Research questions mapping

| RQ | Status | Where |
|----|--------|-------|
| RQ1: Safe substitutes under constraints | Partial — allergen filter works, nutritional delta not yet implemented | `graph/query.py` → `substitutes()` |
| RQ2: What makes ingredients similar | Done — three signals computed and combined | `graph/similarity.py` |
| RQ3: Cuisine and culinary role filtering | Not started | `graph/cuisine.py` (to be built) |
