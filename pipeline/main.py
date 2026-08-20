import os
import sys
import logging
from dotenv import load_dotenv

from src.ingestion.outlook_reader import OutlookIngestor
from src.ingestion.attachment_processor import AttachmentProcessor
from src.extraction.deepseek_client import DeepSeekClient
from src.vector_store.chroma_manager import ChromaManager
from src.graph_generator.obsidian_formatter import ObsidianFormatter

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Configurações Essenciais
load_dotenv() # Carrega chaves de .env
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

TARGET_ACCOUNTS = [
    "luis.bento@nacionalindustria.com.br",
    "contratos@nacionalindustria.com.br"
]
_PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OBSIDIAN_V2_DIR = os.path.join(_PIPELINE_DIR, "data", "obsidian_v2")
CHROMA_DIR = os.path.join(_PIPELINE_DIR, "data", "db", "chroma")
SQLITE_DB = os.path.join(_PIPELINE_DIR, "data", "db", "progress.sqlite")

# Limite de e-mails por sessão
BATCH_LIMIT = 50000

def main(test_mode: bool = False, limit_per_folder: int = 50, since_date: str = None):
    logger.info(f"=== INICIANDO PIPELINE (LIMITE: {limit_per_folder} POR PASTA | DESDE: {since_date or 'INICIO'}) ===")

    # Validação de Chaves API
    if not DEEPSEEK_API_KEY:
        logger.error("ERRO FATAL: Chave de API não encontrada no arquivo .env")
        logger.error("Certifique-se de configurar DEEPSEEK_API_KEY.")
        return

    # 1. Inicializa Módulos
    ingestor = OutlookIngestor(target_accounts=TARGET_ACCOUNTS, db_path=SQLITE_DB)
    # Aumentamos um pouco o budget para o teste de 50 e-mails por pasta
    deepseek = DeepSeekClient(api_key=DEEPSEEK_API_KEY, max_budget=5.00) 
    chroma = ChromaManager(persist_dir=CHROMA_DIR)
    obsidian = ObsidianFormatter(output_dir=OBSIDIAN_V2_DIR)
    
    # 2. Roda o Loop Principal no formato Generator
    emails_processed_in_session = 0
    
    # Passamos o limite por pasta e a data de corte para o ingestor
    for email_data in ingestor.process_emails(test_mode=test_mode, limit_per_folder=limit_per_folder, since_date=since_date):
        msg_id = email_data["id"]
        logger.info(f"Processando Mensagem [{msg_id}]: {email_data.get('subject', 'Sem assunto')}...")
        
        # 2.1 Concatena o texto do corpo + Texto dos anexos (extraídos via MarkItDown)
        raw_text_payload = f"Remetente: {email_data.get('sender')}\nAssunto: {email_data.get('subject')}\n"
        if email_data.get('conversation_topic'):
            raw_text_payload += f"Thread: {email_data.get('conversation_topic')}\n"
        raw_text_payload += f"\nCorpo do E-mail:\n{email_data.get('body', '')}\n\n"
        
        try:
            if email_data.get("attachments"):
                raw_text_payload += "--- ANEXOS DO E-MAIL (Convertidos via MarkItDown + Docling) ---\n"
                for att in email_data["attachments"]:
                    att_text = AttachmentProcessor.process(att)
                    att["extracted_text"] = att_text
                    raw_text_payload += f"\n- Arquivo: {att['name']}\n{att_text}\n"

            # Proteção contra textos estupidamente grandes (Limita a ~80k caracteres para o LLM)
            raw_text_payload = raw_text_payload[:80000]

            # 2.2 DeepSeek: Bypass da Fase 1 (O LLM fará o trabalho na Fase 4 com o neo4j_sync_v4.py)
            extracted_json = {}
            
                
            # 2.3 Obsidian: Cria os nós visuais e salva no disco IMEDIATAMENTE (Prioridade 1)
            md_path = obsidian.create_markdown(email_data, extracted_json)
            logger.info(f"[+] Markdown gerado: {os.path.basename(md_path)}")
                
            # 2.4 ChromaDB: Salva texto e contexto nos vetores
            # BYPASS FASE 4.2: ChromaDB completamente silenciado para evitar Timeout no Google Embeddings
            # Se for necessário no futuro, criaremos script de vetorização próprio lendo de 'obsidian/'
            pass
            
            
            # 2.5 Persiste sucesso
            ingestor.db.mark_processed(msg_id, email_data["subject"], email_data["date"], "SUCCESS")
            emails_processed_in_session += 1
            
        except Exception as e:
            if "Budget Exceeded" in str(e):
                logger.warning("FIM DA SESSÃO: Orçamento atingido.")
                break
            logger.error(f"Erro imprevisto ao processar e-mail {msg_id}: {e}")
            ingestor.db.mark_processed(msg_id, email_data["subject"], email_data["date"], f"FAILED: {str(e)}")

        # Limite global de segurança
        if emails_processed_in_session >= BATCH_LIMIT:
            logger.info(f"Limite global de {BATCH_LIMIT} e-mails atingido. Finalizando.")
            break

    logger.info("=== PIPELINE FINALIZADO ===")
    logger.info(f"Total de e-mails processados: {emails_processed_in_session}")
    logger.info(f"Custo LLM da sessão: ${deepseek.total_cost:.4f}")

if __name__ == "__main__":
    import traceback
    try:
        # Garante que as pastas cruciais do script existem
        os.makedirs(OBSIDIAN_V2_DIR, exist_ok=True)
        
        # Executa o lote ilimitado de 2026 para todas as pastas suportadas
        main(test_mode=False, limit_per_folder=0, since_date="2026-01-01")
    except Exception:
        logger.error("ERRO FATAL NO SCRIPT PRINCIPAL:")
        logger.error(traceback.format_exc())
        sys.exit(1)
