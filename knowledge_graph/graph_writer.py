"""
knowledge_graph/graph_writer.py

Adds ONE paper and its extracted entities to the existing Neo4j graph,
without touching anything already there. Deliberately separate from
knowledge_graph/build_graph.py, which clears the ENTIRE graph before
rebuilding it — reusing that script for a single upload would wipe out
the whole shared knowledge graph you and your partner built together.

Uses MERGE (Neo4j's "create if it doesn't already exist" pattern)
throughout, so calling this multiple times for the same paper is safe
and never creates duplicates.
"""


def add_paper_to_graph(driver, paper_id, title, entities, authors=None):
    """
    entities: dict with keys "diseases", "drugs", "genes", "organizations",
    each a list of entity name strings — the same shape produced by
    nlp/extract_entities.py's extract_entities_for_paper().
    """
    entity_type_map = {
        "diseases": "Disease",
        "drugs": "Drug",
        "genes": "Gene",
        "organizations": "Organization",
    }

    with driver.session() as session:
        session.run(
            "MERGE (p:Paper {paper_id: $paper_id}) SET p.title = $title",
            paper_id=paper_id, title=title,
        )

        if authors:
            for author in authors:
                session.run(
                    """
                    MERGE (a:Author {name: $name})
                    WITH a
                    MATCH (p:Paper {paper_id: $paper_id})
                    MERGE (a)-[:AUTHORED]->(p)
                    """,
                    name=author, paper_id=paper_id,
                )

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
                    name=name, paper_id=paper_id,
                )

    total_entities = sum(len(entities.get(k, [])) for k in entity_type_map)
    return total_entities
