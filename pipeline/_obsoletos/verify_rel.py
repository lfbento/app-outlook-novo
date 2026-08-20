from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "caracol_admin")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
with driver.session() as session:
    # Vamos ver quem o documento 185 (anterior ao 186/187/188) citou
    # Nota: No log, o índice é i+1. Então o arquivo antes do 186/187/188 é o 185.
    # Vou buscar documentos que foram citados por outros.
    res = session.run("""
        MATCH (d1:Documento)-[:CITA]->(d2:Documento)
        WHERE d2.id IN ['94003a97a5da3da', '7ae6ae55173a4f9', '324375a983a0f00']
        RETURN d1.id as origin, d2.id as target
    """).data()
    print(res)
driver.close()
