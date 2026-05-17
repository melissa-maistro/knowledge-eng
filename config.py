"""
Shared paths and settings for all pipelines.
Edit DATA_DIR if you want to store raw data elsewhere.
"""
from pathlib import Path

ROOT       = Path(__file__).parent
DATA_RAW   = ROOT / "data" / "raw"
DATA_PROC  = ROOT / "data" / "processed"
DATA_TRIP  = ROOT / "data" / "triples"

# ── USDA ──────────────────────────────────────────────────────────────────────
# Download: https://fdc.nal.usda.gov/download-datasets -> Foundation Foods ZIP
# Unzip into data/raw/
USDA_DIR               = DATA_RAW
USDA_FOOD_CSV          = USDA_DIR / "food.csv"
USDA_CATEGORY_CSV      = USDA_DIR / "food_category.csv"
USDA_NUTRIENT_CSV      = USDA_DIR / "nutrient.csv"
USDA_FOOD_NUTRIENT_CSV = USDA_DIR / "food_nutrient.csv"

# ── FlavorDB ──────────────────────────────────────────────────────────────────
# Scraped automatically by pipelines/flavordb.py — no manual download needed
FLAVORDB_ENTITIES_CSV  = DATA_PROC / "flavordb_entities.csv"
FLAVORDB_MOLECULES_CSV = DATA_PROC / "flavordb_molecules.csv"
FLAVORDB_LINKS_CSV     = DATA_PROC / "flavordb_links.csv"

# ── Open Food Facts ───────────────────────────────────────────────────────────
# Download: https://world.openfoodfacts.org/data
# -> en.openfoodfacts.org.products.csv (~9 GB uncompressed)
# Place in data/raw/
OFF_DIR = DATA_RAW
OFF_CSV = OFF_DIR / "en.openfoodfacts.org.products.csv"

# ── Food.com ──────────────────────────────────────────────────────────────────
# Download: https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions
# Place RAW_recipes.csv in data/raw/
FOODCOM_DIR     = DATA_RAW
FOODCOM_RECIPES = FOODCOM_DIR / "RAW_recipes.csv"

# ── Output triple files ───────────────────────────────────────────────────────
TRIPLE_NUTRIENTS     = DATA_TRIP / "nutrients.csv"
TRIPLE_FLAVOUR       = DATA_TRIP / "flavour.csv"
TRIPLE_ALLERGENS     = DATA_TRIP / "allergens.csv"
TRIPLE_COOCCURRENCE  = DATA_TRIP / "cooccurrence.csv"
TRIPLE_SIMILARITY    = DATA_TRIP / "similarity.csv"   # computed last, from the others

# ── Neo4j (optional) ──────────────────────────────────────────────────────────
NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "password"   # change this
