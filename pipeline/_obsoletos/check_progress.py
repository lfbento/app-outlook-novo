import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "caracol_admin")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        doc_count = session.run("MATCH (d:Documento) RETURN count(d) as c").single()["c"]
        thread_count = session.run("MATCH (t:Thread) RETURN count(t) as c").single()["c"]
        total_nodes = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
        equip_count = session.run("MATCH (e:Equipamento) RETURN count(e) as c").single()["c"]
        
        print(json.dumps({
            "status": "online",
            "progress_docs": doc_count,
            "total_files": 613,
            "threads": thread_count,
            "equipamentos": equip_count,
            "total_nodes": total_nodes
        }))
    driver.close()
except Exception as e:
    print(json.dumps({"status": "offline", "error": str(e)}))
