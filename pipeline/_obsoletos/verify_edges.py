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
    print("=== RELACIONAMENTOS DO PUMPING TANK ===")
    res = session.run("""
        MATCH (e:Equipamento {id: 'NC-CNC-T01'})-[r]-(n)
        RETURN type(r) as Edge, labels(n)[0] as Node_Label, n.id as ID
    """).data()
    print(json.dumps(res, indent=2, ensure_ascii=False))
driver.close()
