"""
test_connections.py

Run this after setting up your .env file to confirm all three cloud
services (Neo4j, Postgres, Groq) are reachable and working, BEFORE
writing any real project logic. This is your "environment is ready"
checkpoint.

Usage:
    python test_connections.py
"""

import os
from dotenv import load_dotenv

load_dotenv()


def test_neo4j():
    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")

        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 'Neo4j connected' AS message")
            message = result.single()["message"]
        driver.close()
        print(f"[PASS] Neo4j: {message}")
        return True
    except Exception as e:
        print(f"[FAIL] Neo4j: {e}")
        return False


def test_postgres():
    try:
        import psycopg2
        url = os.getenv("POSTGRES_URL")
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT 'Postgres connected';")
        message = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"[PASS] Postgres: {message}")
        return True
    except Exception as e:
        print(f"[FAIL] Postgres: {e}")
        return False


def test_groq():
    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
        )
        response = llm.invoke("Reply with exactly: Groq connected")
        print(f"[PASS] Groq: {response.content.strip()}")
        return True
    except Exception as e:
        print(f"[FAIL] Groq: {e}")
        return False


if __name__ == "__main__":
    print("Testing all cloud connections...\n")
    results = {
        "Neo4j": test_neo4j(),
        "Postgres": test_postgres(),
        "Groq": test_groq(),
    }

    print("\n--- Summary ---")
    all_passed = all(results.values())
    for service, passed in results.items():
        print(f"{service}: {'OK' if passed else 'NOT WORKING'}")

    if all_passed:
        print("\nAll services connected. Your environment is ready.")
    else:
        print("\nSome services failed. Fix these before moving on to actual project code.")
