import os
import json
import glob
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger("CARACOL-LOADER")

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "caracol_admin")

def salvar_no_neo4j(doc_id: str, data: dict, session):
    """Realiza a persistência das entidades e relações extraídas."""
    try:
        # 1. Garantir Documento
        session.run("MERGE (d:Documento {id: $doc_id})", doc_id=doc_id)

        # 2. Persistir Nós
        nodes = data.get("nodes", [])
        for node in nodes:
            nid = node.get("id")
            label = node.get("label", "Entidade").replace(" ", "_").replace("-", "_")
            props = node.get("properties", {})
            
            # Limpeza de chaves das propriedades
            clean_props = {str(k).replace(" ", "_"): v for k, v in props.items()}
            clean_props["id"] = nid
            
            query = f"MERGE (n:{label} {{id: $nid}}) SET n += $props"
            session.run(query, nid=nid, props=clean_props)
            
            # Link com o documento
            session.run(f"MATCH (d:Documento {{id: $doc_id}}), (n:{label} {{id: $nid}}) MERGE (d)-[:CITA]->(n)", 
                        doc_id=doc_id, nid=nid)

        # 3. Persistir Relações
        edges = data.get("edges", [])
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            etype = edge.get("type", "RELACIONADO_A").replace(" ", "_").upper()
            eprops = edge.get("properties", {})

            if source and target:
                query = f"""
                MATCH (s {{id: $source}}), (t {{id: $target}})
                MERGE (s)-[r:{etype}]->(t)
                SET r += $props
                """
                session.run(query, source=source, target=target, props=eprops)
        
        return True
    except Exception as e:
        logger.error(f"Erro Neo4j no doc {doc_id}: {e}")
        return False

def main():
    extraction_dir = "pipeline/data/extractions"
    if not os.path.exists(extraction_dir):
        logger.error(f"Diretório de extrações não encontrado: {extraction_dir}")
        return

    json_files = sorted(glob.glob(os.path.join(extraction_dir, "*.json")))
    total = len(json_files)
    logger.info(f"Iniciando Loader. Encontrados {total} arquivos para processar.")

    def get_driver():
        return GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            connection_timeout=60.0,
            max_connection_lifetime=300.0,
            max_connection_pool_size=10,
            keep_alive=True,
            connection_acquisition_timeout=60.0
        )

    driver = get_driver()
    
    for i, filepath in enumerate(json_files):
        doc_id = os.path.basename(filepath).replace(".json", "")
        
        success = False
        retries = 0
        max_retries = 3
        
        while not success and retries < max_retries:
            try:
                with driver.session() as session:
                    # Checkpoint: Só processa se não estiver INGESTADO
                    result = session.run("MATCH (d:Documento {id: $doc_id}) RETURN d.status_loader as status", doc_id=doc_id)
                    record = result.single()
                    if record and record["status"] == "INGESTADO":
                        success = True
                        continue

                    logger.info(f"[{i+1}/{total}] Carregando: {doc_id} (Tentativa {retries+1})")
                    
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    if salvar_no_neo4j(doc_id, data, session):
                        session.run("""
                            MATCH (d:Documento {id: $doc_id})-[:CITA]->(p:Projeto) 
                            MATCH (d)-[:CITA]->(e:Equipamento) 
                            MERGE (e)-[:PERTENCE_A]->(p)
                        """, doc_id=doc_id)
                        
                        session.run("MATCH (d:Documento {id: $doc_id}) SET d.status_loader = 'INGESTADO', d.carregado_em = datetime()", doc_id=doc_id)
                        logger.info(f"✅ [{i+1}/{total}] {doc_id} Ingestado.")
                        success = True
                
                time.sleep(2.0)
                
            except Exception as e:
                retries += 1
                logger.warning(f"⚠️ Erro de rede no arquivo {doc_id}: {e}. Retentativa {retries}/{max_retries}...")
                time.sleep(5)
                # Tenta fechar e recriar o driver em caso de erro crítico de serviço
                try:
                    driver.close()
                except:
                    pass
                driver = get_driver()

    driver.close()
    logger.info("LOADER (ESTÁGIO 2) FINALIZADO.")

if __name__ == "__main__":
    main()
