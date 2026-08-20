import os
import json
import logging
import pika
import sqlite3
import time
from dotenv import load_dotenv

from src.ingestion.attachment_processor import AttachmentProcessor
from src.graph_generator.obsidian_formatter import ObsidianFormatter

# Configuração de Logs - Agora grava em arquivo e no console
_PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(_PIPELINE_DIR, "consumer.log")

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

OBSIDIAN_V2_DIR = os.path.join(_PIPELINE_DIR, "data", "obsidian_v2")
SQLITE_DB = os.path.join(_PIPELINE_DIR, "data", "db", "progress.sqlite")

os.makedirs(OBSIDIAN_V2_DIR, exist_ok=True)
obsidian = ObsidianFormatter(output_dir=OBSIDIAN_V2_DIR)

def update_db_status(msg_id: str, subject: str, date: str, status: str):
    """Atualiza o sqlite de status independentemente."""
    try:
        with sqlite3.connect(SQLITE_DB) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO processed_emails (id, subject, date, status)
                VALUES (?, ?, ?, ?)
            ''', (msg_id, subject, date, status))
            conn.commit()
    except Exception as e:
        logger.error(f"Erro ao atualizar DB: {e}")

def process_message(ch, method, properties, body):
    try:
        email_data = json.loads(body)
        msg_id = email_data.get("id", "undefined")
        logger.info(f"Consumindo Mensagem [{msg_id[:16]}]: {email_data.get('subject', '')[:50]}...")
        
        # [Early ACK] - Confirma o recebimento imediatamente para evitar o timeout de 30 minutos
        try:
            if ch.is_open:
                ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Erro no ACK antecipado: {e}")

        # Extração de Anexos
        raw_text_payload = f"Remetente: {email_data.get('sender')}\nAssunto: {email_data.get('subject')}\n"
        if email_data.get('conversation_topic'):
            raw_text_payload += f"Thread: {email_data.get('conversation_topic')}\n"
        raw_text_payload += f"\nCorpo do E-mail:\n{email_data.get('body', '')}\n\n"
        
        if email_data.get("attachments"):
            raw_text_payload += "--- ANEXOS DO E-MAIL (Convertidos via MarkItDown + Docling) ---\n"
            for att in email_data["attachments"]:
                att_text = AttachmentProcessor.process(att)
                att["extracted_text"] = att_text
                raw_text_payload += f"\n- Arquivo: {att['name']}\n{att_text}\n"

        raw_text_payload = raw_text_payload[:80000]

        # Obsidian: Cria os nós visuais e salva no disco
        md_path = obsidian.create_markdown(email_data, {})
        logger.info(f"[+] Markdown gerado: {os.path.basename(md_path)}")
        
        update_db_status(msg_id, email_data["subject"], email_data["date"], "SUCCESS")
        
    except Exception as e:
        logger.error(f"Erro imprevisto ao processar e-mail: {e}")
        try:
            update_db_status(msg_id, email_data.get("subject", ""), email_data.get("date", ""), f"FAILED: {str(e)}")
        except Exception:
            pass


def run_consumer():
    logger.info("Conectando ao RabbitMQ...")
    credentials = pika.PlainCredentials('guest', 'guest')
    parameters = pika.ConnectionParameters(
        host='127.0.0.1', 
        port=5672, 
        virtual_host='/', 
        credentials=credentials,
        heartbeat=60,  # Heartbeat ativado para manter conexão viva
        blocked_connection_timeout=300
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue='outlook_ingestion', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='outlook_ingestion', on_message_callback=process_message)
    
    logger.info("Aguardando na fila 'outlook_ingestion'...")
    channel.start_consuming()

def main():
    logger.info("=== INICIANDO CONSUMER V4.1 (ROBUSTO) ===")
    
    while True:
        try:
            run_consumer()
        except KeyboardInterrupt:
            logger.info("Consumer interrompido pelo usuario.")
            break
        except pika.exceptions.AMQPConnectionError:
            logger.warning("Conexão com RabbitMQ perdida. Tentando reconectar em 10 segundos...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Erro inesperado no Consumer: {e}")
            logger.info("Reiniciando em 10 segundos...")
            time.sleep(10)

if __name__ == "__main__":
    main()

