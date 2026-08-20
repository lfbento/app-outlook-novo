"""
Enriquecimento Universal (Moedas, Unidades, Quantidades) v4.0 - $0 / < 5 minutos
Lê tabelas Markdown, detecta colunas financeiras e de medidas, limpa os dados
e injeta as propriedades diretamente nos nós do Neo4j.

Correções v4.0:
- Regex pré-compiladas no nível do módulo (B2)
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
RE_NON_NUMERIC = re.compile(r"[^\d,\.\-]")

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


def parse_monetario(raw: str) -> tuple[float, str]:
    """Retorna (valor_float, moeda_str) a partir de uma string suja."""
    if not raw or str(raw).strip() in ("", "nan", "NaN", "-"):
        return None, None
    raw = str(raw).strip().upper()

    moeda = "BRL"
    if "USD" in raw or "$" in raw and "R$" not in raw: moeda = "USD"
    if "EUR" in raw or "€" in raw: moeda = "EUR"

    # Regex pré-compilada (B2)
    numeros = RE_NON_NUMERIC.sub("", raw)
    if not numeros:
        return None, None

    if ',' in numeros and '.' in numeros:
        if numeros.rfind(',') > numeros.rfind('.'):
            numeros = numeros.replace('.', '').replace(',', '.')
        else:
            numeros = numeros.replace(',', '')
    elif ',' in numeros:
        numeros = numeros.replace(',', '.')

    try:
        val = float(numeros)
        return val, moeda
    except ValueError:
        return None, None


def parse_quantidade(raw: str, col_name: str) -> tuple[float, str]:
    """Retorna (quantidade_float, unidade_str) baseado na celula e no nome da coluna."""
    if not raw or str(raw).strip() in ("", "nan", "NaN", "-"):
        return None, None
    raw = str(raw).strip().lower()
    col_name = str(col_name).lower()

    unidade = "un"
    if "kg" in col_name or "kg" in raw: unidade = "kg"
    elif "ton" in col_name or "ton" in raw: unidade = "ton"
    elif " m" in col_name or "metro" in col_name or " m" in raw: unidade = "m"
    elif "m2" in col_name or "m²" in col_name or "m2" in raw: unidade = "m2"
    elif "m3" in col_name or "m³" in col_name or "m3" in raw: unidade = "m3"
    elif "pç" in col_name or "pc" in col_name or "peça" in col_name or "pç" in raw: unidade = "pç"
    elif "kit" in col_name or "kit" in raw: unidade = "kit"
    elif "peso" in col_name: unidade = "kg"

    # Regex pré-compilada (B2)
    numeros = RE_NON_NUMERIC.sub("", raw)
    if not numeros:
        return None, None

    if ',' in numeros and '.' in numeros:
        if numeros.rfind(',') > numeros.rfind('.'):
            numeros = numeros.replace('.', '').replace(',', '.')
        else:
            numeros = numeros.replace(',', '')
    elif ',' in numeros:
        numeros = numeros.replace(',', '.')

    try:
        val = float(numeros)
        return val, unidade
    except ValueError:
        return None, None


def extrair_tabelas(filepath: str) -> list[dict]:
    """Extrai registros tabulares identificando quem eh quem e suas medidas."""
    registros = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        logger.warning(f"Erro ao ler {filepath}: {e}")
        return registros

    in_table = False
    headers = []
    col_mappings = {}

    for line in lines:
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            cols = [c.strip() for c in line.split("|")[1:-1]]

            if all(c.replace('-', '').strip() == '' for c in cols if c):
                continue

            if not in_table:
                headers = cols
                col_mappings = {
                    "id_col": -1, "val_col": -1, "peso_col": -1, "qtd_col": -1
                }

                for i, h in enumerate(headers):
                    hl = h.lower()
                    if "tag" in hl or "item" == hl or "nome" in hl or "identifica" in hl or "descri" in hl:
                        col_mappings["id_col"] = i if col_mappings["id_col"] == -1 else col_mappings["id_col"]
                        if "tag" in hl: col_mappings["id_col"] = i
                    if "valor" in hl or "preço" in hl or "preco" in hl or "price" in hl or "total" in hl or "r$" in hl:
                        col_mappings["val_col"] = i
                    if "peso" in hl or "weight" in hl or "kg" in hl or "ton" in hl:
                        col_mappings["peso_col"] = i
                    if "qtd" in hl or "quant" in hl or "qty" in hl or "saldo" in hl:
                        col_mappings["qtd_col"] = i

                if col_mappings["id_col"] != -1 and (col_mappings["val_col"] != -1 or col_mappings["peso_col"] != -1 or col_mappings["qtd_col"] != -1):
                    in_table = True
            else:
                if len(cols) <= col_mappings["id_col"]:
                    continue
                identifier = cols[col_mappings["id_col"]]
                if not identifier or identifier in ("nan", "NaN", "-"):
                    continue

                registro = {"id_match": identifier}

                if col_mappings["val_col"] != -1 and col_mappings["val_col"] < len(cols):
                    val, moeda = parse_monetario(cols[col_mappings["val_col"]])
                    if val is not None:
                        registro["valor"] = val
                        registro["moeda"] = moeda

                if col_mappings["peso_col"] != -1 and col_mappings["peso_col"] < len(cols):
                    val, unid = parse_quantidade(cols[col_mappings["peso_col"]], headers[col_mappings["peso_col"]])
                    if val is not None:
                        registro["quantidade"] = val
                        registro["unidade"] = unid
                elif col_mappings["qtd_col"] != -1 and col_mappings["qtd_col"] < len(cols):
                    val, unid = parse_quantidade(cols[col_mappings["qtd_col"]], headers[col_mappings["qtd_col"]])
                    if val is not None:
                        registro["quantidade"] = val
                        registro["unidade"] = unid

                if len(registro) > 1:
                    registros.append(registro)
        else:
            in_table = False

    return registros


# ==========================================
# B4: Batch write via UNWIND
# ==========================================
def atualizar_neo4j_batch(registros: list[dict], session) -> int:
    """Atualiza nós no Neo4j usando UNWIND para batching."""
    if not registros:
        return 0

    # Separa em dois tipos de batch: com valor e com quantidade
    batch_valor = []
    batch_qtd = []

    for reg in registros:
        entry = {"id": reg["id_match"]}
        if "valor" in reg:
            entry["valor"] = reg["valor"]
            entry["moeda"] = reg["moeda"]
            batch_valor.append(entry)
        if "quantidade" in reg:
            entry_qtd = {"id": reg["id_match"], "quantidade": reg["quantidade"], "unidade": reg["unidade"]}
            batch_qtd.append(entry_qtd)

    total = 0

    if batch_valor:
        query = """
        UNWIND $batch AS row
        MATCH (n)
        WHERE (n.tag = row.id OR n.nome = row.id OR n.id = row.id
               OR n.nome CONTAINS row.id OR n.tag CONTAINS row.id)
          AND (n:Equipamento OR n:Material OR n:Projeto OR n:NotaFiscal OR n:Contrato)
        SET n.valor = row.valor, n.moeda = row.moeda
        RETURN count(n) AS c
        """
        res = session.run(query, batch=batch_valor).single()
        if res: total += res["c"]

    if batch_qtd:
        query = """
        UNWIND $batch AS row
        MATCH (n)
        WHERE (n.tag = row.id OR n.nome = row.id OR n.id = row.id
               OR n.nome CONTAINS row.id OR n.tag CONTAINS row.id)
          AND (n:Equipamento OR n:Material OR n:Projeto OR n:NotaFiscal OR n:Contrato)
        SET n.quantidade = row.quantidade, n.unidade = row.unidade
        RETURN count(n) AS c
        """
        res = session.run(query, batch=batch_qtd).single()
        if res: total += res["c"]

    return total


def main():
    obsidian_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")
    files = sorted(glob.glob(os.path.join(obsidian_dir, "*.md")))
    total = len(files)

    logger.info(f"ENRIQUECIMENTO UNIVERSAL (MOEDAS E UNIDADES) v4.0")
    logger.info(f"Arquivos: {total} | Custo: $0 | Sem LLM")
    logger.info(f"Correções: regex pré-compiladas | batch UNWIND | driver em função")
    logger.info("=" * 60)

    total_registros = 0
    total_atualizados = 0
    arquivos_com_dados = 0
    batch_buffer = []
    BATCH_SIZE = 200

    driver = get_driver()

    try:
        with driver.session() as session:
            for i, f in enumerate(files):
                registros = extrair_tabelas(f)
                if not registros:
                    continue

                arquivos_com_dados += 1
                total_registros += len(registros)
                batch_buffer.extend(registros)

                if len(batch_buffer) >= BATCH_SIZE:
                    n = atualizar_neo4j_batch(batch_buffer, session)
                    total_atualizados += n
                    batch_buffer = []
                    if i % 50 == 0:
                        logger.info(f"[{i+1}/{total}] Progresso... ({total_atualizados} nos atualizados ate agora)")

            # Flush final
            if batch_buffer:
                n = atualizar_neo4j_batch(batch_buffer, session)
                total_atualizados += n

        # Auditoria Final
        with driver.session() as session:
            v = session.run("MATCH (n) WHERE n.valor IS NOT NULL RETURN count(n) AS c").single()["c"]
            q = session.run("MATCH (n) WHERE n.quantidade IS NOT NULL RETURN count(n) AS c").single()["c"]
            logger.info("\n" + "=" * 60)
            logger.info("RESULTADO FINAL DO NEO4J")
            logger.info("=" * 60)
            logger.info(f"Arquivos com dados tabulares processados: {arquivos_com_dados}")
            logger.info(f"Registros tabulares encontrados: {total_registros}")
            logger.info(f"Nos Neo4j enriquecidos nesta execucao global: {total_atualizados}")
            logger.info(f"-> Total Absoluto de Nos com 'valor/moeda'   : {v}")
            logger.info(f"-> Total Absoluto de Nos com 'quantidade/unidade': {q}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
