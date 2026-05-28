# Ingredient Substitution Knowledge Graph
**Group 3 — Knowledge Engineering Project**
Client: Western European outpatient dietetics clinic

---

## What this project does

We built a knowledge graph that answers the question:
*"When a patient needs to remove or reduce an ingredient from a home-cooked recipe, what can they safely substitute it with — given their allergies, nutritional goals, and the dish they are cooking?"*

The graph combines four data sources to produce scored, traceable substitution suggestions for each ingredient query.

---

## Project structure

```
knowledge-eng/
├── config.py
├── requirements.txt
├── dashboard.py                    ← Dash web interface (http://127.0.0.1:8050)
├── data/
│   ├── raw/                        ← original downloads, never modify these
│   ├── processed/
│   │   ├── canonical_ingredients.csv   ← 272 ingredients with functional_class, USDA match, etc.
│   │   └── ...
│   └── triples/
│       ├── nutrients.csv
│       ├── allergens.csv
│       ├── cooccurrence.csv
│       └── similarity.csv          ← 1,839 scored SIMILAR_TO edges
├── pipelines/
│   ├── flavordb.py
│   ├── usda.py
│   ├── normalise.py                ← builds canonical list, USDA matching, functional_class
│   ├── curated_allergens.py        ← EU Big-14 allergen mapping
│   └── foodcom.py
├── graph/
│   ├── similarity.py               ← computes SIMILAR_TO edges with category filter
│   ├── query.py                    ← SubstitutionGraph: loads graph, answers RQ1/2/3
│   └── substitution.py             ← PatientConsultation: patient-facing query layer
└── evaluation/
    ├── gold_standard.csv           ← 19 manually verified substitution pairs
    └── tune_weights.py             ← grid search over scoring weights (MRR, H@5, H@10)
```

---

## Data sources

| Source | What we use it for | License |
|--------|-------------------|---------|
| **FlavorDB2** (IIIT Delhi) | Flavour molecule links, ~936 whole ingredients | CC BY-NC-SA 3.0 |
| **USDA FoodData Central** Foundation Foods | Nutrient values per 100g | CC0 |
| **Food.com** (Kaggle) | Ingredient co-occurrence from 230k recipes | Kaggle |
| **Curated allergen table** | EU Big-14 allergen mapping per ingredient | Hand-mapped |

FlavorDB CSVs should be placed in `data/raw/`. USDA and Food.com files are downloaded separately (see Setup).

---

## Graph at a glance

- **272 canonical ingredient nodes** — whole foods from FlavorDB, filtered to Western European diet
- **1,839 SIMILAR_TO edges** — pairs scored above threshold
- **Allergens** — EU Big-14 framework, curated at ingredient level via `pipelines/curated_allergens.py`

---

## How similarity is computed

`graph/similarity.py` computes a `SIMILAR_TO` score for each ingredient pair using four signals:

| Signal | Source | Weight | How |
|--------|--------|--------|-----|
| Macro similarity | USDA | 0.90 | Cosine similarity on fat/carb/protein calorie ratios |
| Full nutrition | USDA | 0.05 | Cosine similarity on full nutrient vector |
| Recipe co-occurrence | Food.com | 0.05 | Normalised co-occurrence across 230k recipes |
| Flavour similarity | FlavorDB | 0.00 | Jaccard on shared flavour molecules |

### Category filter

A pair is only kept if both ingredients share the same **functional class**:

- `fat_source` — calories ≥ 50% from fat
- `carb_source` — calories ≥ 50% from carbohydrates
- `protein_source` — calories ≥ 30% from protein

Functional class is derived from macronutrient calorie ratios. One cross-class exception is allowed: `vegetable_tuber` ↔ `vegetable_root` pairs are preserved to capture starchy vegetable substitutions.

---

## Research questions

| RQ | Status | Where |
|----|--------|-------|
| RQ1: Safe substitutes under constraints | Done — allergen filter + nutritional delta annotations | `graph/substitution.py` → `PatientConsultation` |
| RQ2: What makes ingredients similar | Done — four signals, explainable via `query.explain()` | `graph/similarity.py`, `graph/query.py` |
| RQ3: Cuisine-aware filter | Partial — Food.com co-occurrence signal included at 5% weight; full cuisine tagging not implemented | `graph/query.py` |

---

## Evaluation

Evaluation uses a gold standard of **19 manually verified substitution pairs** (`evaluation/gold_standard.csv`).

| Metric | Score |
|--------|-------|
| MRR | 0.31 |
| H@5 | 0.42 |
| H@10 | 0.68 |

Weight tuning is done via grid search in `evaluation/tune_weights.py`.

**Known limitation:** Chicken→Turkey ranks at position 16 in the raw graph because lean fish share a similar macro profile to chicken. In practice, the allergen and functional-class filters improve this ranking for real patient queries.

---

## Dashboard

A Dash web interface is provided for interactive substitution queries:

```bash
python dashboard.py
```

Opens at `http://127.0.0.1:8050`.

---

## Setup

```bash
pip install -r requirements.txt
```

### Run order

```bash
python pipelines/flavordb.py
python pipelines/usda.py
python pipelines/normalise.py
python pipelines/curated_allergens.py
python pipelines/foodcom.py
python graph/similarity.py
python dashboard.py          # web interface on http://127.0.0.1:8050
```

> **Note:** Running `normalise.py` regenerates `canonical_ingredients.csv` from scratch. Any manual patches to `functional_class` or USDA matches must be re-applied afterward.

### Data downloads required

| File | Where | Place in |
|------|-------|----------|
| USDA Foundation Foods ZIP | https://fdc.nal.usda.gov/download-datasets | `data/raw/` |
| Food.com `RAW_recipes.csv` | https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions | `data/raw/` |

FlavorDB CSVs should already be in `data/raw/`.
