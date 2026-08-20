"""Teste integrado com Outlook — processa 5 emails com a nova pipeline."""
import os
import sys
import logging

sys.path.insert(0, 'c:/bento/prg/app-outlook-novo/pipeline')
os.environ['PYTHONIOENCODING'] = 'utf-8'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from src.ingestion.outlook_reader import OutlookIngestor
from src.ingestion.attachment_processor import AttachmentProcessor
from src.graph_generator.obsidian_formatter import ObsidianFormatter

TARGET_ACCOUNTS = ['luis.bento@nacionalindustria.com.br']
SQLITE_DB = 'c:/bento/prg/app-outlook-novo/pipeline/data/db/progress_v2_test.sqlite'
OBSIDIAN_V2 = 'c:/bento/prg/app-outlook-novo/pipeline/data/obsidian_v2'

os.makedirs(OBSIDIAN_V2, exist_ok=True)

print("=== TESTE INTEGRADO v2 — Pipeline Hibrida ===\n")

ingestor = OutlookIngestor(target_accounts=TARGET_ACCOUNTS, db_path=SQLITE_DB)
obsidian = ObsidianFormatter(output_dir=OBSIDIAN_V2)

count = 0
MAX_EMAILS = 2

for email_data in ingestor.process_emails(test_mode=False, limit_per_folder=3, since_date='2026-03-01'):
    msg_id = email_data['id']
    subject = email_data.get('subject', 'Sem assunto')
    print(f"\n[{count+1}] {subject[:70]}")

    if email_data.get('attachments'):
        print(f"    {len(email_data['attachments'])} anexo(s):")
        for att in email_data['attachments']:
            att_name = att.get('name', 'desconhecido')
            att_text = AttachmentProcessor.process(att)
            att['extracted_text'] = att_text
            text_len = len(att_text) if att_text else 0
            preview = att_text[:100].replace('\n', ' ') if att_text else '[vazio]'
            print(f"    -> {att_name} ({text_len} chars)")
            if text_len > 0:
                print(f"       Preview: {preview}...")
    else:
        print("    Sem anexos")

    md_path = obsidian.create_markdown(email_data, {})
    print(f"    MD: {os.path.basename(md_path)}")

    ingestor.db.mark_processed(msg_id, subject, email_data['date'], 'SUCCESS')
    count += 1
    if count >= MAX_EMAILS:
        break

print(f"\n=== TESTE CONCLUIDO: {count} emails processados ===")
print(f"MDs gerados em: {OBSIDIAN_V2}")

# Listar MDs gerados
mds = [f for f in os.listdir(OBSIDIAN_V2) if f.endswith('.md')]
print(f"Total de MDs na pasta: {len(mds)}")
