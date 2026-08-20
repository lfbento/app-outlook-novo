"""
Enriquecimento Direto de Datas v3.0 — Sem LLM, Sem Re-processamento
Lê as tabelas dos Markdowns com regex/pandas e atualiza data_entrega no Neo4j.
Custo: $0 | Tempo estimado: < 5 minutos
"""
import os
import re
import glob
import logging
from datetime import datetime
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# Conexão Neo4j
# ============================================================
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "caracol_admin"))

# ============================================================
# Helpers de normalização de data
# ============================================================
def normalizar_data(raw: str) -> str:
    """Converte vários formatos de data para YYYY-MM-DD."""
    if not raw or str(raw).strip() in ("", "nan", "NaT", "NaN"):
        return None
    raw = str(raw).strip()
    # Já no formato YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS
    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)
    # DD/MM/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # DD/MM/YY (ex: 03/03/26)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})$", raw)
    if m:
        d, mo, y = m.groups()
        year = int(y) + 2000
        return f"{year}-{int(mo):02d}-{int(d):02d}"
    return None

# ============================================================
# Padrões de extração
# ============================================================

# Padrão 1: "TAG: 510-015 - ENTREGA: 15/01/2026"
PAT_TAG_ENTREGA = re.compile(
    r"TAG:\s*([\w\-\.]+)\s*-\s*ENTREGA:\s*([\d/]+)",
    re.IGNORECASE
)

# Padrão 2: "NOME - ILHA: xxx - TAG: yyy - ENTREGA: DD/MM/YYYY"
PAT_NOME_TAG_ENTREGA = re.compile(
    r"([\w\s]+?)\s*-\s*ILHA:\s*[\w]+\s*-\s*TAG:\s*([\w\-\.]+)\s*-\s*ENTREGA:\s*([\d/]+)",
    re.IGNORECASE
)

# Padrão 3: Coluna PRAZO ENT. nas tabelas Markdown (pipe-separated)
# | ITEM | ... | TAG EQP. | ... | PRAZO ENT. | ...
# | 1.0  | ... | 510-015  | ... | 2026-01-15 | ...
PAT_TABLE_HEADER = re.compile(r"\|\s*PRAZO\s*ENT\.", re.IGNORECASE)
PAT_TABLE_ROW = re.compile(r"^\|\s*[\d\.]+\s*\|", re.MULTILINE)

# ============================================================
# Extração principal
# ============================================================
def extrair_dados_de_markdown(filepath: str) -> list[dict]:
    """
    Retorna lista de {tag, nome, data_entrega} encontrados no Markdown.
    """
    results = []
    seen_tags = set()

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"[SKIP] Erro lendo {filepath}: {e}")
        return results

    # ---- Padrão 1 e 2: regex no texto corrido ----
    for m in PAT_NOME_TAG_ENTREGA.finditer(content):
        nome, tag, data_raw = m.groups()
        data = normalizar_data(data_raw)
        if data and tag not in seen_tags:
            results.append({"tag": tag.strip(), "nome": nome.strip(), "data_entrega": data})
            seen_tags.add(tag.strip())

    for m in PAT_TAG_ENTREGA.finditer(content):
        tag, data_raw = m.groups()
        data = normalizar_data(data_raw)
        if data and tag not in seen_tags:
            results.append({"tag": tag.strip(), "nome": None, "data_entrega": data})
            seen_tags.add(tag.strip())

    # ---- Padrão 3: tabelas Markdown com coluna PRAZO ENT. ----
    lines = content.split("\n")
    header_idx = None
    tag_col = None
    nome_col = None
    prazo_col = None

    for i, line in enumerate(lines):
        if PAT_TABLE_HEADER.search(line):
            # encontrou header da tabela
            cols = [c.strip().upper() for c in line.split("|")]
            # localizar índices das colunas importantes
            for ci, col in enumerate(cols):
                if "TAG EQP" in col or col == "TAG":
                    tag_col = ci
                if "IDENTIFICA" in col or "NOME" in col or "IDENTIFICAÇÃO" in col:
                    nome_col = ci
                if "PRAZO ENT" in col or "PRAZO" in col:
                    prazo_col = ci
            header_idx = i
            break

    if header_idx is not None and prazo_col is not None:
        for line in lines[header_idx + 2:]:  # pula header e separador ---
            if not line.strip().startswith("|"):
                break
            cols = line.split("|")
            if len(cols) <= max(filter(None, [tag_col, prazo_col, nome_col]), default=0):
                continue
            try:
                prazo_raw = cols[prazo_col].strip() if prazo_col and prazo_col < len(cols) else ""
                tag_raw = cols[tag_col].strip() if tag_col and tag_col < len(cols) else ""
                nome_raw = cols[nome_col].strip() if nome_col and nome_col < len(cols) else ""

                data = normalizar_data(prazo_raw)
                if not data or not tag_raw or tag_raw in ("nan", "NaN", ""):
                    continue

                # Pega última data se houver múltiplas (ex: "15/01/2026\n27/02/2026\n03/03/2026")
                datas_multiplas = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", prazo_raw)
                if datas_multiplas:
                    data = normalizar_data(datas_multiplas[-1])  # última data = mais recente

                if tag_raw not in seen_tags:
                    results.append({
                        "tag": tag_raw,
                        "nome": nome_raw if nome_raw not in ("nan", "") else None,
                        "data_entrega": data
                    })
                    seen_tags.add(tag_raw)
            except Exception:
                continue

    return results

# ============================================================
# Atualização no Neo4j
# ============================================================
def atualizar_neo4j(registros: list[dict], session) -> tuple[int, int]:
    """Atualiza data_entrega nos nós existentes por TAG ou NOME. Retorna (atualizados, criados)."""
    atualizados = 0

    for reg in registros:
        tag = reg["tag"]
        nome = reg.get("nome")
        data = reg["data_entrega"]

        # Tenta por TAG primeiro
        res = session.run(
            "MATCH (e:Equipamento) WHERE e.tag = $tag "
            "SET e.data_entrega = $data RETURN count(e) AS c",
            tag=tag, data=data
        ).single()
        n = res["c"] if res else 0

        # Se não achou por tag, tenta por NOME (CONTAINS)
        if n == 0 and nome:
            res = session.run(
                "MATCH (e:Equipamento) WHERE e.nome CONTAINS $nome "
                "SET e.data_entrega = $data RETURN count(e) AS c",
                nome=nome, data=data
            ).single()
            n = res["c"] if res else 0

        if n > 0:
            atualizados += n
            logger.debug(f"  [{tag}] {nome} -> {data} ({n} nós)")

    return atualizados

# ============================================================
# Main
# ============================================================
def main():
    obsidian_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")
    files = sorted(glob.glob(os.path.join(obsidian_dir, "*.md")))
    total = len(files)

    logger.info(f"ENRIQUECIMENTO DE DATAS v3.0")
    logger.info(f"Arquivos: {total} | Custo: $0 | Sem LLM")
    logger.info("=" * 60)

    total_registros = 0
    total_atualizados = 0
    arquivos_com_dados = 0

    with driver.session() as session:
        for i, f in enumerate(files):
            registros = extrair_dados_de_markdown(f)
            if not registros:
                continue

            arquivos_com_dados += 1
            total_registros += len(registros)
            n_atualizados = atualizar_neo4j(registros, session)
            total_atualizados += n_atualizados

            if n_atualizados > 0:
                logger.info(f"[{i+1}/{total}] {os.path.basename(f)[:60]}")
                logger.info(f"  Encontrados: {len(registros)} | Atualizados: {n_atualizados} nós")
                for r in registros[:3]:
                    logger.info(f"    TAG={r['tag']} | {r['nome']} | {r['data_entrega']}")

    # Verificação final
    with driver.session() as session:
        total_com_data = session.run(
            "MATCH (e:Equipamento) WHERE e.data_entrega IS NOT NULL RETURN count(e) AS c"
        ).single()["c"]

        # Amostra dos dados enriquecidos
        sample = session.run(
            "MATCH (e:Equipamento) WHERE e.data_entrega IS NOT NULL "
            "RETURN e.id, e.nome, e.tag, e.data_entrega ORDER BY e.data_entrega LIMIT 10"
        )
        logger.info("\n" + "=" * 60)
        logger.info("RESULTADO FINAL")
        logger.info("=" * 60)
        logger.info(f"Arquivos com datas extraídas: {arquivos_com_dados}")
        logger.info(f"Registros encontrados: {total_registros}")
        logger.info(f"Nós Neo4j atualizados: {total_atualizados}")
        logger.info(f"Equipamentos com data_entrega no grafo: {total_com_data}")
        logger.info("\nAmostra dos equipamentos com data_entrega:")
        for r in sample:
            logger.info(f"  {r['e.data_entrega']} | {r['e.nome']} | TAG: {r['e.tag']} | {r['e.id']}")

    driver.close()

if __name__ == "__main__":
    main()
