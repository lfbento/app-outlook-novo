import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from src.ingestion.outlook_reader import OutlookIngestor
from src.ingestion.attachment_processor import AttachmentProcessor
from src.extraction.deepseek_client import DeepSeekClient
from src.vector_store.chroma_manager import ChromaManager
from src.graph_generator.obsidian_formatter import ObsidianFormatter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DEBUG")

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TARGET_ACCOUNTS = ["luis.bento@nacionalindustria.com.br"]
OBSIDIAN_DIR = "data/obsidian_test"
CHROMA_DIR = "data/db/chroma_test"
SQLITE_DB = "data/db/progress_test.sqlite"

def debug():
    logger.info("Iniciando depuração...")
    ingestor = OutlookIngestor(target_accounts=TARGET_ACCOUNTS, db_path=SQLITE_DB)
    deepseek = DeepSeekClient(api_key=DEEPSEEK_API_KEY, max_budget=1.00)
    chroma = ChromaManager(persist_dir=CHROMA_DIR)
    obsidian = ObsidianFormatter(output_dir=OBSIDIAN_DIR)
    
    logger.info("Buscando primeiro e-mail...")
    for email_data in ingestor.process_emails(limit_per_folder=1):
        msg_id = email_data["id"]
        logger.info(f"Processando: {email_data['subject']}")
        
        raw_text_payload = f"Subject: {email_data['subject']}\nBody: {email_data['body'][:1000]}"
        
        logger.info("Chamando DeepSeek...")
        extracted_json = deepseek.extract_entities(raw_text_payload)
        logger.info("DeepSeek OK.")
        
        logger.info("Chamando ChromaDB...")
        try:
            chroma.add_documents(
                documents=[raw_text_payload],
                metadatas=[{"test": True}],
                ids=[msg_id]
            )
            logger.info("ChromaDB OK.")
        except Exception as e:
            logger.error(f"ChromaDB FALHOU: {e}")
            raise e
            
        logger.info("Chamando Obsidian...")
        try:
            md_path = obsidian.create_markdown(email_data, extracted_json)
            logger.info(f"Obsidian OK: {md_path}")
        except Exception as e:
            logger.error(f"Obsidian FALHOU: {e}")
            raise e
            
        logger.info("Sucesso total no debug!")
        break

if __name__ == "__main__":
    debug()
