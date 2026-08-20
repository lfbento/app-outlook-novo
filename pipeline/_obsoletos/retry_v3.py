"""
Retry v3.0 - Re-processa SOMENTE os Markdowns que nao estao no Neo4j
(os 388 que falharam durante a queda do Docker)
"""
import os
import sys
import glob
import logging
import time

sys.path.append(os.getcwd())

from src.ingestion.neo4j_sync import Neo4jSync

def retry_failed():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    logger = logging.getLogger(__name__)
    
    obsidian_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")
    files = sorted(glob.glob(os.path.join(obsidian_dir, "*.md")))
    total = len(files)
    
    sync = Neo4jSync(max_budget=2.00)
    
    # Conta quantos ja estao no Neo4j
    ja_processados = len(sync.processed_ids)
    pendentes = total - ja_processados
    
    logger.info(f"RETRY v3.0: {total} arquivos total, {ja_processados} ja processados, {pendentes} pendentes")
    
    start = time.time()
    sucesso = 0
    erros = 0
    pulados = 0
    
    for i, f in enumerate(files):
        doc_id = os.path.basename(f).replace(".md", "")
        
        if sync.is_already_processed(doc_id):
            pulados += 1
            continue
        
        try:
            logger.info(f"[{i+1}/{total}] Processando {os.path.basename(f)}...")
            sync.process_markdown(f)
            sucesso += 1
        except Exception as e:
            if "Budget Exceeded" in str(e):
                logger.warning(f"ORCAMENTO ESGOTADO apos {sucesso} arquivos!")
                break
            logger.error(f"Erro: {e}")
            erros += 1
    
    elapsed = time.time() - start
    logger.info(f"\n{'='*60}")
    logger.info(f"RETRY v3.0 CONCLUIDO")
    logger.info(f"Pulados (ja existiam): {pulados}")
    logger.info(f"Sucesso: {sucesso}")
    logger.info(f"Erros: {erros}")
    logger.info(f"Tempo: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    logger.info(f"Custo: ${sync.deepseek.total_cost:.4f}")
    logger.info(f"{'='*60}")
    
    sync.close()

if __name__ == "__main__":
    retry_failed()
