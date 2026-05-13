"""
graph/load.py
Optional: bulk-loads all triple files into Neo4j.
Requires Neo4j running locally, or update NEO4J_URI in config.py.

Install driver: pip install neo4j
Start Neo4j:    https://neo4j.com/download/  (Desktop) or via Docker:
                docker run -p 7474:7474 -p 7687:7687 neo4j:latest
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
                    TRIPLE_NUTRIENTS, TRIPLE_ALLERGENS,
                    TRIPLE_COOCCURRENCE, TRIPLE_SIMILARITY,
                    FLAVORDB_LINKS_CSV, FLAVORDB_MOLECULES_CSV)

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: pip install neo4j")
    sys.exit(1)

BATCH = 500   # rows per transaction


def batch_run(session, query, rows):
    for i in range(0, len(rows), BATCH):
        session.run(query, rows=rows[i:i+BATCH])


def load_flavour(session):
    links = pd.read_csv(FLAVORDB_LINKS_CSV).to_dict("records")
    batch_run(session, """
        UNWIND $rows AS r
        MERGE (i:Ingredient {name: r.entity_name})
          SET i.category = r.category
        MERGE (m:FlavourMolecule {pubchem_id: r.pubchem_id})
          SET m.name = r.molecule_name
        MERGE (i)-[:CONTAINS_MOLECULE]->(m)
    """, links)
    print(f"  Loaded {len(links)} flavour links")


def load_similarity(session):
    df = pd.read_csv(TRIPLE_SIMILARITY).to_dict("records")
    batch_run(session, """
        UNWIND $rows AS r
        MERGE (a:Ingredient {name: r.ingredient_a})
        MERGE (b:Ingredient {name: r.ingredient_b})
        MERGE (a)-[s:SIMILAR_TO]->(b)
          SET s.score = r.score,
              s.reason = r.reason,
              s.flavour_score = r.flavour_score,
              s.shared_molecules = r.shared_molecules
    """, df)
    print(f"  Loaded {len(df)} similarity edges")


def load_allergens(session):
    df = pd.read_csv(TRIPLE_ALLERGENS).to_dict("records")
    batch_run(session, """
        UNWIND $rows AS r
        MERGE (i:Ingredient {name: r.subject})
        MERGE (al:Allergen {name: r.object})
        MERGE (i)-[:HAS_ALLERGEN]->(al)
    """, df)
    print(f"  Loaded {len(df)} allergen edges")


def load_nutrients(session):
    df = pd.read_csv(TRIPLE_NUTRIENTS).to_dict("records")
    batch_run(session, """
        UNWIND $rows AS r
        MERGE (i:Ingredient {name: r.subject})
        MERGE (n:Nutrient {name: r.relation_target})
        MERGE (i)-[h:HAS_NUTRIENT]->(n)
          SET h.amount_per_100g = r.amount
    """, df)
    print(f"  Loaded {len(df)} nutrient edges")


def run():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # create indexes first
        session.run("CREATE INDEX ingredient_name IF NOT EXISTS FOR (i:Ingredient) ON (i.name)")
        session.run("CREATE INDEX allergen_name IF NOT EXISTS FOR (a:Allergen) ON (a.name)")

        if FLAVORDB_LINKS_CSV.exists():
            print("Loading FlavorDB flavour links...")
            load_flavour(session)
        if TRIPLE_SIMILARITY.exists():
            print("Loading similarity edges...")
            load_similarity(session)
        if TRIPLE_ALLERGENS.exists():
            print("Loading allergen edges...")
            load_allergens(session)
        if TRIPLE_NUTRIENTS.exists():
            print("Loading nutrient edges...")
            load_nutrients(session)

    driver.close()
    print("\nNeo4j load complete.")
    print("Open http://localhost:7474 to browse the graph.")
    print("\nExample Cypher query:")
    print("""
  MATCH (i:Ingredient {name: 'Butter'})-[s:SIMILAR_TO]->(c:Ingredient)
  WHERE NOT (c)-[:HAS_ALLERGEN]->(:Allergen {name: 'dairy'})
  RETURN c.name, s.score, s.reason
  ORDER BY s.score DESC LIMIT 10
    """)


if __name__ == "__main__":
    run()
