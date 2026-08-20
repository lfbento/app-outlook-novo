from neo4j import GraphDatabase
import json
import os
from dotenv import load_dotenv

load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "caracol_admin")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
with driver.session() as session:
    print("=== DADOS EXTRAÍDOS PELO DEEPSEEK V3.2 NO ARQUIVO 18/03 ===")
    res = session.run("""
        MATCH (d:Documento)-[r]->(n)
        RETURN labels(n)[0] as tipo, n.id as entidade_id, properties(n) as props
        ORDER BY tipo
    """).data()
    with open("output_v3.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
driver.close()
