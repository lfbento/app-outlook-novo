"""
Enriquecimento Universal de Datas v4.0 - $0 / < 5 minutos
Busca datas em múltiplos formatos e colunas genéricas ("data", "entrega", "prazo", "vencimento", "deadline")

Correções v4.0:
- Regex pré-compiladas no nível do módulo (B2)
- Removido re.DOTALL catastrófico do PAT_DATA_GENERIC (B1)
- Batch writes via UNWIND no Neo4j (B4)
- Driver movido para função get_driver() (C1)
- Conexão com timeouts e pool configurado (A4)
"""
import os
import re
import glob
import logging
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# Regex pré-compiladas (B2)
# ==========================================
RE_DATE_ISO = re.compile(r"(\d{4}[-/]\d{2}[-/]\d{2})")
RE_DATE_BR = re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})")
RE_YYYY_SLASH = re.compile(r"(\d{4})/(\d{2})/(\d{2})")
RE_DDMM_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_DDMMYY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2})$")

# B1: SEM re.DOTALL - o .*? agora opera por LINHA, sem backtracking exponencial
RE_DATA_GENERIC = re.compile(
    r"(?:tag|nome|equipamento|projeto|fatura|nf|nota)\s*[:\-]?\s*([\w\-\.]+).*?"
    r"(?:entrega|prazo|data|vencimento)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    re.IGNORECASE
)


# ==========================================
# Driver factory (C1 + A4)
# ==========================================
def get_driver():
    return GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "caracol_admin"),
        connection_timeout=60.0,
        max_connection_lifetime=300.0,
        max_connection_pool_size=10,
        keep_alive=True,
        connection_acquisition_timeout=60.0
    )


def normalizar_data(raw: str) -> str:
    """Extrai e converte data para YYYY-MM-DD."""
    if not raw or str(raw).strip() in ("", "nan", "NaT", "NaN", "-"):
        return None
    raw = str(raw).strip()

    # Tenta ISO primeiro, depois BR (usa regex pré-compiladas)
    matches = RE_DATE_ISO.findall(raw) or RE_DATE_BR.findall(raw)
    if not matches:
        return None

    # Pega a primeira data encontrada
    data_raw = matches[0] if isinstance(matches[0], str) else (matches[0][0] or matches[0][1])
    data_raw = data_raw.replace("-", "/")

    m = RE_YYYY_SLASH.match(data_raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = RE_DDMM_SLASH.match(data_raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    m = RE_DDMMYY_SLASH.match(data_raw)
    if m:
        d, mo, y = m.groups()
        year = int(y) + 2000
        return f"{year}-{int(mo):02d}-{int(d):02d}"

    return None


def extrair_tabelas_data(filepath: str) -> list[dict]:
    registros = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        logger.warning(f"Erro lendo {filepath}: {e}")
        return registros

    in_table = False
    col_mappings = {}

    for line in lines:
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]

            if all(c.replace('-', '').strip() == '' for c in cols if c):
                continue

            if not in_table:
                col_mappings = {"id_col": -1, "data_col": -1}
                for i, h in enumerate(cols):
                    hl = h.lower()
                    if "tag" in hl or "item" == hl or "nome" in hl or "identifica" in hl or "descri" in hl:
                        col_mappings["id_col"] = i if col_mappings["id_col"] == -1 else col_mappings["id_col"]
                        if "tag" in hl:
                            col_mappings["id_col"] = i
                    if any(x in hl for x in ["data", "entrega", "prazo", "vencimento", "deadline", "previs", "chegada"]):
                        col_mappings["data_col"] = i

                if col_mappings["id_col"] != -1 and col_mappings["data_col"] != -1:
                    in_table = True
            else:
                if len(cols) <= max(col_mappings["id_col"], col_mappings["data_col"]):
                    continue

                identifier = cols[col_mappings["id_col"]]
                data_raw = cols[col_mappings["data_col"]]

                if not identifier or identifier in ("nan", "NaN", "-"):
                    continue

                data_limpa = normalizar_data(data_raw)
                if data_limpa:
                    registros.append({
                        "id_match": identifier,
                        "data_entrega": data_limpa
                    })
        else:
            in_table = False

    return registros


def extrair_texto_data(filepath: str) -> list[dict]:
    """Busca em texto corrido pareamentos de Identificador - Data (ex: Equipamento X - entrega 12/12)"""
    registros = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return registros

    # B1: Processa LINHA POR LINHA em vez de conteúdo inteiro com re.DOTALL
    # Isso elimina o backtracking exponencial
    for line in lines:
        m = RE_DATA_GENERIC.search(line)
        if not m:
            continue
        identifier = m.group(1).strip()
        data_raw = m.group(2).strip()
        data_limpa = normalizar_data(data_raw)

        if len(identifier) > 2 and data_limpa:
            registros.append({
                "id_match": identifier,
                "data_entrega": data_limpa
            })

    return registros


# ==========================================
# B4: Batch write via UNWIND
# ==========================================
def atualizar_neo4j_batch(registros: list[dict], session) -> int:
    """Atualiza nós no Neo4j usando UNWIND para batching (muito mais rápido)."""
    if not registros:
        return 0

    query = """
    UNWIND $batch AS row
    MATCH (n)
    WHERE (n.tag = row.id OR n.nome = row.id OR n.id = row.id
           OR n.nome CONTAINS row.id OR n.tag CONTAINS row.id)
      AND (n:Equipamento OR n:Material OR n:Projeto OR n:NotaFiscal OR n:Contrato OR n:Documento)
    SET n.data_entrega = row.data_entrega
    RETURN count(n) AS c
    """
    batch = [{"id": r["id_match"], "data_entrega": r["data_entrega"]} for r in registros]
    res = session.run(query, batch=batch).single()
    return res["c"] if res else 0


def main():
    obsidian_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")
    files = sorted(glob.glob(os.path.join(obsidian_dir, "*.md")))
    total = len(files)

    logger.info(f"ENRIQUECIMENTO UNIVERSAL DE DATAS v4.0")
    logger.info(f"Correções: regex pré-compiladas | batch UNWIND | driver em função")
    logger.info("=" * 60)

    total_registros = 0
    total_atualizados = 0
    arquivos_com_dados = 0
    batch_buffer = []
    BATCH_SIZE = 200  # Acumula registros antes de enviar ao Neo4j

    driver = get_driver()

    try:
        with driver.session() as session:
            for i, f in enumerate(files):
                registros = extrair_tabelas_data(f) + extrair_texto_data(f)

                unicos = {r["id_match"]: r for r in registros}.values()

                if not unicos:
                    continue

                arquivos_com_dados += 1
                total_registros += len(unicos)
                batch_buffer.extend(unicos)

                # Flush quando atingir o tamanho do batch
                if len(batch_buffer) >= BATCH_SIZE:
                    n = atualizar_neo4j_batch(batch_buffer, session)
                    total_atualizados += n
                    batch_buffer = []
                    if i % 50 == 0:
                        logger.info(f"[{i+1}/{total}] Progresso... ({total_atualizados} nos atualizados)")

            # Flush final
            if batch_buffer:
                n = atualizar_neo4j_batch(batch_buffer, session)
                total_atualizados += n

        with driver.session() as session:
            t = session.run("MATCH (n) WHERE n.data_entrega IS NOT NULL RETURN count(n) AS c").single()["c"]
            logger.info(f"Arquivos com datas processados: {arquivos_com_dados}")
            logger.info(f"Registros encontrados: {total_registros}")
            logger.info(f"Nos Neo4j enriquecidos: {total_atualizados}")
            logger.info(f"Total Absoluto de Nos com 'data_entrega': {t}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
