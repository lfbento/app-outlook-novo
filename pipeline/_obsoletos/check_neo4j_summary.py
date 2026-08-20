import os
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "caracol_admin"

def check_db():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            # Listar labels existentes
            print("--- Labels no Banco ---")
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
            print(labels)

            # Query para Empresas e Projetos
            # Tentando labels comuns (Empresa, Projeto)
            print("\n--- Empresas e seus Projetos Relacionados ---")
            query = """
            MATCH (e) WHERE any(l IN labels(e) WHERE l =~ '(?i)Empresa.*')
            OPTIONAL MATCH (e)-[r]-(p) WHERE any(l IN labels(p) WHERE l =~ '(?i)Projeto.*')
            RETURN e.name AS empresa, collect(DISTINCT p.name) AS projetos
            """
            result = session.run(query)
            
            found = False
            for record in result:
                found = True
                empresa = record["empresa"] or "Empresa sem Nome"
                projetos = record["projetos"]
                print(f"Empresa: {empresa}")
                if projetos and any(projetos):
                    print(f"  Projetos: {', '.join(filter(None, projetos))}")
                else:
                    print("  Projetos: Nenhum projeto detectado diretamente nesta relação.")
            
            if not found:
                print("Nenhuma empresa encontrada com as labels esperadas.")

    except Exception as e:
        print(f"Erro ao conectar ou consultar o Neo4j: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    check_db()
