"""
Reprocessamento Total v3.0 - Re-ingere todos os Markdowns com prompt enriquecido
Extrai: datas de entrega, valores monetarios, unidades de medida
"""
import os
import sys
import glob
import logging
import time

sys.path.append(os.getcwd())

from src.ingestion.neo4j_sync import Neo4jSync

def reprocess_all():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    logger = logging.getLogger(__name__)
    
    obsidian_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")
    files = sorted(glob.glob(os.path.join(obsidian_dir, "*.md")))
    total = len(files)
    
    logger.info(f"REPROCESSAMENTO v3.0: {total} arquivos para re-ingerir")
    logger.info("Novo prompt inclui: data_entrega, valor+moeda, quantidade+unidade")
    
    # Budget generoso para reprocessar todos
    sync = Neo4jSync(max_budget=2.00)
    
    # Limpa o cache de IDs processados para forcar reprocessamento
    sync.processed_ids = set()
    
    # Primeiro, limpar os nos antigos de cada documento
    logger.info("Limpando nos antigos para permitir re-extracao...")
    with sync.driver.session() as session:
        # Remove apenas os nos extraidos (nao Documento/Thread)
        # Marca documentos como nao-processados deletando-os
        for i, f in enumerate(files):
            doc_id = os.path.basename(f).replace(".md", "")
            session.run(
                "MATCH (d:Documento {id: $id}) DETACH DELETE d",
                id=doc_id
            )
            if (i + 1) % 100 == 0:
                logger.info(f"  Limpeza: {i+1}/{total}")
    
    logger.info("Limpeza concluida. Iniciando re-ingestao com prompt v3.0...")
    
    start = time.time()
    sucesso = 0
    erros = 0
    
    for i, f in enumerate(files):
        try:
            logger.info(f"[{i+1}/{total}] Re-processando {os.path.basename(f)}...")
            sync.process_markdown(f)
            sucesso += 1
        except Exception as e:
            if "Budget Exceeded" in str(e):
                logger.warning(f"ORCAMENTO ESGOTADO apos {sucesso} arquivos!")
                break
            logger.error(f"Erro ao processar {f}: {e}")
            erros += 1
    
    elapsed = time.time() - start
    logger.info(f"\n{'='*60}")
    logger.info(f"REPROCESSAMENTO v3.0 CONCLUIDO")
    logger.info(f"Sucesso: {sucesso}/{total}")
    logger.info(f"Erros: {erros}")
    logger.info(f"Tempo: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    logger.info(f"Custo: ${sync.deepseek.total_cost:.4f}")
    logger.info(f"{'='*60}")
    
    sync.close()

if __name__ == "__main__":
    reprocess_all()
