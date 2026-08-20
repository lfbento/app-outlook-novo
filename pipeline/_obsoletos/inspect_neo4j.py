import os
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "caracol_admin"

def inspect_nodes():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            print("--- Inspeção de Nós de Empresa ---")
            query = "MATCH (n:Empresa) RETURN n LIMIT 5"
            result = session.run(query)
            for record in result:
                node = record["n"]
                print(f"ID: {node.get('id')}, Labels: {list(node.labels)}, Props: {dict(node)}")

            print("\n--- Inspeção de Nós de Projeto ---")
            query = "MATCH (n:Projeto) RETURN n LIMIT 5"
            result = session.run(query)
            for record in result:
                node = record["n"]
                print(f"ID: {node.get('id')}, Labels: {list(node.labels)}, Props: {dict(node)}")
                
            print("\n--- Relações entre Empresa e Projeto ---")
            query = "MATCH (e:Empresa)-[r]-(p:Projeto) RETURN e, type(r) as rel, p LIMIT 5"
            result = session.run(query)
            for record in result:
                e = record["e"]
                p = record["p"]
                print(f"Empresa({e.get('name') or e.get('id')}) -[{record['rel']}]-> Projeto({p.get('name') or p.get('id')})")

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    inspect_nodes()
