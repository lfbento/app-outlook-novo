import os
import glob
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "caracol_admin"
OBSIDIAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")

def clear_neo4j():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # 1. Encontrar todos os IDs de documentos no Obsidian que possuam anexo
    updated_doc_ids = []
    
    files = glob.glob(os.path.join(OBSIDIAN_DIR, "*.md"))
    for f in files:
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
            if "## 📎 Anexos (Textos Extraídos)" in content:
                # O doc_id no neo4j é literalmente o basename sem o .md, igual ao obsidian_formatter salvou
                doc_id = os.path.basename(f).replace(".md", "")
                updated_doc_ids.append(doc_id)
                
    print(f"Total de arquivos MD com anexos atualizados encontrados: {len(updated_doc_ids)}")
    
    if not updated_doc_ids:
        print("Nenhum arquivo para invalidar o cache.")
        return
        
    print("Deletando a marcação de 'Documento' no Neo4j para forçar releitura...")
    deleted_count = 0
    with driver.session() as session:
        for doc_id in updated_doc_ids:
            # Apaga apenas o nó do Documento. Os nós filhos (Pessoas, Empresas) e as relações deles ficam.
            # Como a próxima passagem usa MERGE, ela refará as relações sem duplicar.
            res = session.run("MATCH (d:Documento {id: $id}) DETACH DELETE d RETURN count(d)", id=doc_id)
            deleted_count += res.single()[0]
            
    print(f"Total de nós de Documentos limpos do cache do Neo4j: {deleted_count}")
    print("Agora você pode rodar a Fase 2 (neo4j_sync.py) com segurança e ele re-lerá os anexos!")

if __name__ == "__main__":
    clear_neo4j()
