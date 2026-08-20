"""
Configuração central do Pipeline CARACOL.
Todos os caminhos são relativos à raiz do projeto.
Funciona em Windows e Linux.
"""
import os

# Raiz do projeto = pasta pipeline/
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))

# Raiz do projeto (um nível acima da pasta pipeline/)
PROJECT_DIR = os.path.dirname(PIPELINE_DIR)

# Caminhos de dados
OBSIDIAN_DIR = os.path.join(PIPELINE_DIR, "data", "obsidian")
OBSIDIAN_V2_DIR = os.path.join(PIPELINE_DIR, "data", "obsidian_v2")
EXTRACTIONS_DIR = os.path.join(PIPELINE_DIR, "data", "extractions")
CHROMA_DIR = os.path.join(PIPELINE_DIR, "data", "db", "chroma")
SQLITE_DB = os.path.join(PIPELINE_DIR, "data", "db", "progress.sqlite")

# Docling (CPU-only para 8GB RAM + MX330)
DOCLING_TIMEOUT = 60        # segundos máx. por PDF
DOCLING_USE_GPU = False      # MX330 insuficiente para AI models

# Limites de segurança para arquivos compactados
ARCHIVE_MAX_SIZE = 50 * 1024 * 1024      # 50MB total extraído
ARCHIVE_MAX_DEPTH = 2                     # níveis de recursão
ARCHIVE_MAX_FILES = 100                   # arquivos por archive

# Neo4j
NEO4J_BOLT_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_HTTP_URL = os.getenv("NEO4J_HTTP_URL", "http://127.0.0.1:7474/db/neo4j/tx/commit")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "caracol_admin")

# Driver factory
def get_neo4j_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(
        NEO4J_BOLT_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        connection_timeout=60.0,
        max_connection_lifetime=300.0,
        max_connection_pool_size=10,
        keep_alive=True,
        connection_acquisition_timeout=60.0
    )
