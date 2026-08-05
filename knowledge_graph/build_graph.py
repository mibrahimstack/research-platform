"""
knowledge_graph/build_graph.py

The "Knowledge Graph Builder" module from the case study.

Reads paper metadata (data/papers/metadata.jsonl) and extracted entities
(data/processed/entities.jsonl), then inserts everything into Neo4j as:

    (Author)-[:AUTHORED]->(Paper)-[:MENTIONS]->(Disease/Drug/Gene/Organization)

Run from the project root:
    python knowledge_graph/build_graph.py
"""

import json
import os
from dotenv import load_dotenv # type:ignore
from neo4j import GraphDatabase # type:ignore

load_dotenv()

METADATA_FILE = "data/papers/metadata.jsonl"
ENTITIES_FILE = "data/processed/entities.jsonl"


def load_jsonl(filepath):
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def clear_graph(session):
    """Wipes the graph clean so re-running this script doesn't duplicate data."""
    session.run("MATCH (n) DETACH DELETE n")


def create_constraints(session):
    """Ensures no duplicate nodes for the same paper/entity name."""
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Drug) REQUIRE d.name IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (g:Gene) REQUIRE g.name IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (o:Organization) REQUIRE o.name IS UNIQUE")


def insert_paper_and_authors(session, paper_meta):
    session.run(
        """
        MERGE (p:Paper {paper_id: $paper_id})
        SET p.title = $title, p.year = $year, p.journal = $journal, p.doi = $doi
        """,
        paper_id=paper_meta.get("pmcid"),
        title=paper_meta.get("title", ""),
        year=paper_meta.get("year", ""),
        journal=paper_meta.get("journal", ""),
        doi=paper_meta.get("doi", ""),
    )

    author_string = paper_meta.get("authors", "")
    if author_string:
        # Author strings are usually comma-separated
        authors = [a.strip() for a in author_string.split(",") if a.strip()]
        for author in authors:
            session.run(
                """
                MERGE (a:Author {name: $name})
                WITH a
                MATCH (p:Paper {paper_id: $paper_id})
                MERGE (a)-[:AUTHORED]->(p)
                """,
                name=author,
                paper_id=paper_meta.get("pmcid"),
            )


def insert_entities(session, entity_record):
    paper_id = entity_record["paper_id"]
    entities = entity_record["entities"]

    entity_type_map = {
        "diseases": "Disease",
        "drugs": "Drug",
        "genes": "Gene",
        "organizations": "Organization",
    }

    for key, label in entity_type_map.items():
        for name in entities.get(key, []):
            name = name.strip()
            if not name:
                continue
            session.run(
                f"""
                MERGE (e:{label} {{name: $name}})
                WITH e
                MATCH (p:Paper {{paper_id: $paper_id}})
                MERGE (p)-[:MENTIONS]->(e)
                """,
                name=name,
                paper_id=paper_id,
            )


def main():
    if not os.path.exists(METADATA_FILE):
        print(f"ERROR: {METADATA_FILE} not found. Run fetch_papers.py first.")
        return
    if not os.path.exists(ENTITIES_FILE):
        print(f"ERROR: {ENTITIES_FILE} not found. Run nlp/extract_entities.py first.")
        return

    print("Loading metadata and entities...")
    papers_meta = {p["pmcid"]: p for p in load_jsonl(METADATA_FILE) if p.get("pmcid")}
    entity_records = load_jsonl(ENTITIES_FILE)
    print(f"Loaded {len(papers_meta)} papers, {len(entity_records)} entity records.\n")

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )

    with driver.session() as session:
        print("Clearing existing graph data...")
        clear_graph(session)

        print("Creating constraints...")
        create_constraints(session)

        print("Inserting papers and authors...")
        for pmcid, meta in papers_meta.items():
            insert_paper_and_authors(session, meta)

        print("Inserting entities and MENTIONS relationships...")
        for record in entity_records:
            insert_entities(session, record)

        # Quick sanity check
        result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count")
        print("\nGraph summary:")
        for row in result:
            print(f"  {row['label']}: {row['count']}")

    driver.close()
    print("\nDone. Open your Neo4j Aura console and click 'Query' to explore the graph visually.")


if __name__ == "__main__":
    main()
