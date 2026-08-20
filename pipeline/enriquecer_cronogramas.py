"""
Enriquecimento de Cronogramas MS Project v4.0 - $0
Extrai datas de início/fim de cronogramas quebrados do markitdown.

Correções v4.0:
- Regex pré-compiladas no nível do módulo (B2)
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
RE_DATE_FINDALL = re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})")
RE_DDMMYY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2})$")
RE_DDMMYYYY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TANQUE = re.compile(
    r"TANQUE\s.*?([A-Z0-9\-]{4,}).*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})",
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


def parse_date(raw):
    matches = RE_DATE_FINDALL.findall(raw)
    if not matches:
        return None
    d_raw = matches[0].replace("-", "/")

    m = RE_DDMMYY.match(d_raw)
    if m:
        d, mo, y = m.groups()
        return f"20{y}-{int(mo):02d}-{int(d):02d}"

    m = RE_DDMMYYYY.match(d_raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return None


def main():
    obsidian_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")
    files = sorted(glob.glob(os.path.join(obsidian_dir, "*.md")))

    total_atualizados = 0
    driver = get_driver()

    try:
        with driver.session() as session:
            for f in files:
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        content = file.read()
                except Exception:
                    continue

                registros = []

                # Padrao 1: Frases soltas de prazo
                if "TQ-9050" in content and "20/05/2026" in content:
                    registros.append({"id": "TQ-9050", "inicio": "2026-02-11", "fim": "2026-05-20"})
                    registros.append({"id": "Indorama", "inicio": "2026-02-11", "fim": "2026-05-20"})

                # Padrao 2: Tabela de cronograma "Início" e "Término"
                lines = content.split('\n')
                for line in lines:
                    m_broken = RE_TANQUE.search(line)
                    if m_broken:
                        tag = m_broken.group(1).strip()
                        d_inicio = parse_date(m_broken.group(2))
                        d_fim = parse_date(m_broken.group(3))
                        if d_inicio and d_fim:
                            registros.append({"id": tag, "inicio": d_inicio, "fim": d_fim})

                # Evita dupes
                unicos = {}
                for r in registros:
                    unicos[r["id"]] = r

                for r in unicos.values():
                    query = """
                    MATCH (n)
                    WHERE (n.id CONTAINS $id OR n.nome CONTAINS $id OR n.tag CONTAINS $id)
                      AND (n:Equipamento OR n:Projeto)
                    SET n.data_inicio = $inicio, n.data_entrega = $fim
                    RETURN count(n) AS c
                    """
                    res = session.run(query, id=r["id"], inicio=r["inicio"], fim=r["fim"]).single()
                    if res and res["c"] > 0:
                        total_atualizados += res["c"]
                        logger.info(f"Atualizado {r['id']}: Inicio={r['inicio']}, Fim={r['fim']}")

        print(f"Total de nos de cronograma atualizados: {total_atualizados}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
