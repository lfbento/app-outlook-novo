import os
import json
import glob
import logging
import time
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger("CARACOL-LOADER-HTTP")

load_dotenv()

# No HTTP, usamos a porta 7474
NEO4J_HTTP_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "caracol_admin")

auth = HTTPBasicAuth(NEO4J_USER, NEO4J_PASSWORD)

# ==========================================
# Session HTTP com Connection Pooling (CORREÇÃO A1 + A3)
# ==========================================
def _build_session() -> requests.Session:
    """Cria uma requests.Session com retry automático e connection pooling."""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,                    # 0s, 2s, 4s, 8s, 16s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,                 # 10 hosts simultâneos
        pool_maxsize=20,                     # 20 conexões por host
        pool_block=False
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.auth = (NEO4J_USER, NEO4J_PASSWORD)
    return session

_http_session = _build_session()

def run_cypher_http(query, params=None, max_retries=3):
    """Executa uma query individual (usada para checkpoints)."""
    payload = {"statements": [{"statement": query, "parameters": params or {}}]}
    for attempt in range(max_retries):
        try:
            response = _http_session.post(NEO4J_HTTP_URL, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()["results"]
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.warning(f"Conexão falhou (tentativa {attempt+1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)
        except requests.HTTPError as e:
            logger.warning(f"HTTP {e.response.status_code} (tentativa {attempt+1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)
        except (KeyError, ValueError) as e:
            logger.warning(f"Resposta inesperada do Neo4j: {e}")
            return None
    return None

def run_statements_http(statements):
    """Executa múltiplos statements em uma única transação HTTP."""
    payload = {"statements": statements}
    max_retries = 3

    for attempt in range(max_retries):
        try:
            t0 = time.time()
            response = _http_session.post(NEO4J_HTTP_URL, json=payload, timeout=180)
            elapsed = time.time() - t0
            response.raise_for_status()
            data = response.json()
            if data.get("errors"):
                logger.error(f"Erro no Batch HTTP [{elapsed:.2f}s]: {data['errors']}")
                return False
            return True
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.warning(f"Conexão HTTP falhou (tentativa {attempt+1}/{max_retries}): {e}. Reconectando...")
            time.sleep(2 ** (attempt + 1))
        except requests.HTTPError as e:
            logger.warning(f"HTTP {e.response.status_code} (tentativa {attempt+1}/{max_retries}): {e}")
            time.sleep(2 ** (attempt + 1))
    logger.error(f"Falha crítica no Batch HTTP após {max_retries} tentativas.")
    return False

def gerar_statements_doc(doc_id: str, data: dict):
    """Gera a lista de statements Cypher para um documento."""
    stmts = []

    # 1. Garantir Documento
    stmts.append({"statement": "MERGE (d:Documento {id: $doc_id})", "parameters": {"doc_id": doc_id}})

    # 2. Nós
    nodes = data.get("nodes", [])
    for node in nodes:
        nid = node.get("id")
        label = node.get("label", "Entidade").replace(" ", "_").replace("-", "_")
        props = node.get("properties", {})

        # Sanitização profunda de propriedades: Neo4j só aceita primitivos ou arrays de primitivos
        clean_props = {}
        for k, v in props.items():
            key = str(k).replace(" ", "_")
            if isinstance(v, (dict, list)):
                clean_props[key] = json.dumps(v, ensure_ascii=False)
            else:
                clean_props[key] = v
        clean_props["id"] = nid

        stmts.append({
            "statement": f"MERGE (n:`{label}` {{id: $nid}}) SET n += $props",
            "parameters": {"nid": nid, "props": clean_props}
        })
        stmts.append({
            "statement": f"MATCH (d:Documento {{id: $doc_id}}), (n:`{label}` {{id: $nid}}) MERGE (d)-[:CITA]->(n)",
            "parameters": {"doc_id": doc_id, "nid": nid}
        })

    # 3. Relações
    edges = data.get("edges", [])
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        etype = edge.get("type", "RELACIONADO_A").replace(" ", "_").upper()
        eprops = edge.get("properties", {})
        if source and target:
            stmts.append({
                "statement": f"MATCH (s {{id: $source}}), (t {{id: $target}}) MERGE (s)-[r:`{etype}`]->(t) SET r += $props",
                "parameters": {"source": source, "target": target, "props": eprops}
            })

    # 4. Healers e Status
    stmts.append({
        "statement": """
            MATCH (d:Documento {id: $doc_id})-[:CITA]->(p:Projeto)
            MATCH (d)-[:CITA]->(e:Equipamento)
            MERGE (e)-[:PERTENCE_A]->(p)
        """, "parameters": {"doc_id": doc_id}
    })
    stmts.append({
        "statement": "MATCH (d:Documento {id: $doc_id}) SET d.status_loader = 'INGESTADO', d.carregado_em = datetime()",
        "parameters": {"doc_id": doc_id}
    })

    return stmts

def main():
    extraction_dir = "pipeline/data/extractions"
    json_files = sorted(glob.glob(os.path.join(extraction_dir, "*.json")))
    total = len(json_files)
    logger.info(f"Iniciando Loader HTTP SUB-BATCH. {total} arquivos encontrados.")

    for i, filepath in enumerate(json_files):
        doc_id = os.path.basename(filepath).replace(".json", "")

        # Checkpoint rápido
        res = run_cypher_http("MATCH (d:Documento {id: $doc_id}) RETURN d.status_loader as status", {"doc_id": doc_id})
        if res and res[0]["data"] and res[0]["data"][0]["row"] and res[0]["data"][0]["row"][0] == "INGESTADO":
            continue

        logger.info(f"[{i+1}/{total}] Ingerindo (Sub-Batches): {doc_id}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            all_statements = gerar_statements_doc(doc_id, data)

            # Quebrar em sub-batches de 50 statements para não travar o Docker
            chunk_size = 50
            for start_idx in range(0, len(all_statements), chunk_size):
                chunk = all_statements[start_idx : start_idx + chunk_size]

                success = False
                attempts = 0
                while not success and attempts < 3:
                    if run_statements_http(chunk):
                        success = True
                    else:
                        attempts += 1
                        logger.warning(f"Chunk ({start_idx}-{start_idx+len(chunk)}) falhou para {doc_id}. Tentativa {attempts}/3 em 5s...")
                        time.sleep(5)

                if not success:
                    raise Exception(f"Falha persistente no chunk do arquivo {doc_id}")

            logger.info(f"Ingestado com sucesso: {doc_id}")
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Falha definitiva no arquivo {doc_id}: {e}")

    logger.info("LOADER HTTP FINALIZADO.")

if __name__ == "__main__":
    main()
