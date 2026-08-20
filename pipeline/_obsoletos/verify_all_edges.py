from neo4j import GraphDatabase
import os
import json
from dotenv import load_dotenv

load_dotenv()
driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"), auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "caracol_admin")))
with driver.session() as session:
    print("=== TODAS AS ARESTAS DO GRAFO ===")
    res = session.run("MATCH (a)-[r]->(b) RETURN labels(a)[0] as L_A, type(r) as R, labels(b)[0] as L_B, count(r) as C").data()
    print(json.dumps(res, indent=2, ensure_ascii=False))
driver.close()
