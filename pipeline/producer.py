import os
import json
import logging
import pika
import time
import datetime
from dotenv import load_dotenv

from src.ingestion.outlook_reader import OutlookIngestor

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

TARGET_ACCOUNTS = [
    "luis.bento@nacionalindustria.com.br",
    "contratos@nacionalindustria.com.br"
]
_PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(_PIPELINE_DIR, "data", "db", "progress.sqlite")

def main():
    logger.info("=== INICIANDO PRODUCER VIGILANTE (RABBITMQ) ===")

    ingestor = OutlookIngestor(target_accounts=TARGET_ACCOUNTS, db_path=SQLITE_DB)
    
    # Setup RabbitMQ Connection Parameters
    credentials = pika.PlainCredentials('guest', 'guest')
    parameters = pika.ConnectionParameters(
        host='127.0.0.1', 
        port=5672, 
        virtual_host='/', 
        credentials=credentials,
        heartbeat=0,
        blocked_connection_timeout=0
    )

    is_first_run = True
    poll_interval = 60 # segundos

    try:
        while True:
            try:
                # Corte dinâmico
                latest_date_str = ingestor.db.get_latest_processed_date()
                since_date_str = "2026-01-01"
                if latest_date_str:
                    try:
                        latest_date = datetime.datetime.strptime(latest_date_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        safe_cutoff = latest_date - datetime.timedelta(days=2) # 2 dias de margem de segurança
                        since_date_str = safe_cutoff.strftime("%Y-%m-%d %H:%M:%S")
                        if is_first_run:
                            logger.info(f"Última data sinc.: {latest_date_str}. Utilizando cutoff dinâmico: {since_date_str}")
                    except Exception as e:
                        logger.warning(f"Erro parseando latest_date '{latest_date_str}': {e}. Usando default 2026-01-01.")
                else:
                    if is_first_run:
                        logger.info("Banco vazio ou sem sucesso prévio. Sincronizando desde 2026-01-01.")
                
                # Estabelece conexão com RabbitMQ
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                channel.queue_declare(queue='outlook_ingestion', durable=True)

                count = 0
                # Processa inéditos utilizando a data de corte mais recente
                for email_data in ingestor.process_emails(test_mode=False, limit_per_folder=0, since_date=since_date_str):
                    msg_id = email_data["id"]
                    logger.info(f"Enfileirando [{msg_id}]: {email_data.get('subject', 'Sem assunto')}")
                    
                    payload = json.dumps(email_data)
                    
                    channel.basic_publish(
                        exchange='',
                        routing_key='outlook_ingestion',
                        body=payload,
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # persistente
                        )
                    )
                    
                    # Marca como QUEUED
                    ingestor.db.mark_processed(msg_id, email_data["subject"], email_data["date"], "QUEUED")
                    count += 1

                connection.close()

                if count > 0:
                    logger.info(f"Fase de enfileiramento concluída: {count} e-mails enfileirados.")

                if is_first_run:
                    logger.info(f"=== MODO VIGILANTE ATIVO: Monitorando novos e-mails a cada {poll_interval} segundos ===")
                    is_first_run = False

            except Exception as e:
                logger.error(f"Erro inesperado no Produtor Vigilante: {e}")
                logger.info("Retentando no próximo ciclo...")

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        logger.info("Modo vigilante interrompido pelo usuário.")

if __name__ == "__main__":
    main()

