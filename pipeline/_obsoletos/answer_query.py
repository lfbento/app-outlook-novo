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
    res = session.run("""
        MATCH (e:Equipamento)
        WHERE e.data_entrega CONTAINS '03' AND e.data_entrega CONTAINS '2026'
        RETURN e.id as Equipamento, e.data_entrega as Entrega, e.descricao as Descricao, e.tag as Tag
    """).data()
    print(json.dumps(res, indent=2, ensure_ascii=False))
driver.close()
