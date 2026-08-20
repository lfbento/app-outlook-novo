import os
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "caracol_admin"

def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            print("=== ESTATÍSTICAS GERAIS DO NEO4J ===")
            
            # 1. Total de Nós
            result = session.run("MATCH (n) RETURN count(n) as total")
            total_nodes = result.single()["total"]
            print(f"Total de Nós: {total_nodes}")
            
            # 2. Total de Relacionamentos
            result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
            total_rels = result.single()["total"]
            print(f"Total de Relacionamentos: {total_rels}")
            
            # 3. Nós por Label
            print("\n--- Nós por Label ---")
            result = session.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC LIMIT 15")
            for record in result:
                print(f"{record['label']}: {record['count']}")
                
            # 4. Relacionamentos por Tipo
            print("\n--- Relacionamentos por Tipo ---")
            result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC LIMIT 15")
            for record in result:
                print(f"{record['type']}: {record['count']}")
                
            # 5. Amostras de Documentos
            print("\n--- Amostra de Documentos (Emails) ---")
            result = session.run("MATCH (d:Documento) RETURN d LIMIT 3")
            for record in result:
                doc = record["d"]
                print(f"Doc ID: {doc.get('id')[:30]}... | Assunto: {doc.get('assunto')[:50]}...")
                
            # 6. Amostras de Entidades Extraídas (ex: Projeto ou Pessoa ou Empresa)
            print("\n--- Amostra de Entidades Diversas ---")
            result = session.run("MATCH (n) WHERE NOT 'Documento' IN labels(n) RETURN labels(n)[0] as label, n.id as id, properties(n) as props LIMIT 5")
            for record in result:
                print(f"[{record['label']}] ID: {record['id']} | Props: {record['props']}")

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    main()
