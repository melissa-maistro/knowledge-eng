"""
pipelines/flavordb.py
Loads pre-scraped FlavorDB CSVs into the project's processed/ and triples/ folders.
No scraping — uses the files you already generated.

Expected inputs (update paths below if needed):
  flavordb_entities.csv
  flavordb_molecules.csv
  flavordb_links.csv
"""
import sys, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (DATA_PROC, DATA_TRIP,
                    FLAVORDB_ENTITIES_CSV,
                    FLAVORDB_MOLECULES_CSV,
                    FLAVORDB_LINKS_CSV)

# ── Point these at wherever your scraper saved the files ─────────────────────
SOURCE_ENTITIES  = Path("data/raw/flavordb_entities.csv")
SOURCE_MOLECULES = Path("data/raw/flavordb_molecules.csv")
SOURCE_LINKS     = Path("data/raw/flavordb_links.csv")
# ─────────────────────────────────────────────────────────────────────────────

def run():
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    DATA_TRIP.mkdir(parents=True, exist_ok=True)

    for src, dst in [
        (SOURCE_ENTITIES,  FLAVORDB_ENTITIES_CSV),
        (SOURCE_MOLECULES, FLAVORDB_MOLECULES_CSV),
        (SOURCE_LINKS,     FLAVORDB_LINKS_CSV),
    ]:
        if not src.exists():
            raise FileNotFoundError(f"Could not find {src} — update the SOURCE_ paths at the top of this file")
        shutil.copy(src, dst)
        print(f"  Copied {src} -> {dst}")

    print("\nFlavorDB ready.")

if __name__ == "__main__":
    run()