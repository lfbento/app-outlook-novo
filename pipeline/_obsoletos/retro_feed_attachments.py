"""
Retro-feed de anexos — Opção B v2 (Smart Scan via Frontmatter ID)
=================================================================
1. Lê todos os .md existentes no Obsidian
2. Para os que NÃO possuem seção "## 📎 Anexos", lê o `id` do YAML frontmatter
3. Constrói um dicionário {id → filepath} de MDs pendentes
4. Conecta ao Outlook e, para cada pasta, filtra SOMENTE itens com anexo
5. Gera o msg_id do e-mail e verifica se há um MD pendente para ele
6. Extrai o texto dos anexos e appenda no .md
"""
import os
import re
import sys
import glob
import hashlib
import tempfile
import logging

import win32com.client
import pythoncom

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.ingestion.attachment_processor import AttachmentProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

TARGET_ACCOUNTS = [
    "luis.bento@nacionalindustria.com.br",
    "contratos@nacionalindustria.com.br",
    "Arquivos Mortos"
]
OBSIDIAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")

# ── Helpers ─────────────────────────────────────────────────────────
def generate_id(subject: str, date_str: str, sender: str) -> str:
    raw = f"{subject}_{date_str}_{sender}".encode('utf-8', errors='ignore')
    return hashlib.md5(raw).hexdigest()

# ── Passo 1: Lê frontmatter e constrói mapa de pendentes ──────────
def build_pending_map() -> dict:
    """
    Retorna um dict {msg_id: filepath} para cada MD que:
    - NÃO contém a seção de anexos
    - Possui um `id:` no frontmatter YAML
    """
    all_mds = glob.glob(os.path.join(OBSIDIAN_DIR, "*.md"))
    pending = {}
    already_ok = 0
    no_id = 0

    for path in all_mds:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "## 📎 Anexos (Textos Extraídos)" in content:
                already_ok += 1
                continue

            # Extrai o id do YAML frontmatter
            match = re.search(r'^id:\s*(.+)$', content, re.MULTILINE)
            if match:
                msg_id = match.group(1).strip()
                pending[msg_id] = path
            else:
                no_id += 1
        except Exception:
            pass

    logger.info(f"MDs totais: {len(all_mds)} | Já com anexos: {already_ok} | Pendentes com ID: {len(pending)} | Sem ID: {no_id}")
    return pending

# ── Passo 2: Varre o Outlook buscando só e-mails com anexo ────────
def process_outlook(pending_map: dict):
    pythoncom.CoInitialize()
    count_updated = 0

    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

        for account_name in TARGET_ACCOUNTS:
            logger.info(f"Procurando conta: {account_name}")
            account_folder = None
            for i in range(1, outlook.Folders.Count + 1):
                if outlook.Folders.Item(i).Name == account_name:
                    account_folder = outlook.Folders.Item(i)
                    break
            if not account_folder:
                logger.warning(f"Conta '{account_name}' não encontrada. Pulando.")
                continue

            logger.info(f"Varrendo conta: {account_name}")
            count_updated += process_folder(account_folder, pending_map)

            if not pending_map:
                logger.info("Todos os MDs pendentes foram atualizados!")
                break

    finally:
        pythoncom.CoUninitialize()

    return count_updated

def process_folder(folder, pending_map: dict) -> int:
    updated = 0
    folder_name = folder.Name.lower()

    # Ignora pastas não relevantes
    ignored = ['itens excluídos', 'deleted items', 'lixo eletrônico',
               'junk e-mail', 'rascunhos', 'drafts', 'spam']
    if any(ig in folder_name for ig in ignored):
        return 0

    try:
        items = folder.Items
        # Filtra SOMENTE e-mails que possuem anexos usando SQL
        filtered = items.Restrict('@SQL="urn:schemas:httpmail:hasattachment" = 1')
        total = filtered.Count
        if total > 0:
            logger.info(f"  Pasta '{folder.Name}': {total} itens com anexo")

        # Usa GetFirst/GetNext — MUITO mais rápido que Item(i) para coleções grandes
        item = filtered.GetFirst()
        scanned = 0
        while item is not None:
            scanned += 1
            if not pending_map:
                logger.info(f"  Todos pendentes resolvidos! Saindo da pasta.")
                return updated

            if scanned % 500 == 0:
                logger.info(f"  ... Progresso: {scanned}/{total} itens varridos | {updated} atualizados nesta pasta | {len(pending_map)} pendentes globais")

            try:
                if getattr(item, 'Class', 0) != 43:
                    item = filtered.GetNext()
                    continue

                subject = getattr(item, 'Subject', '') or "Sem Assunto"
                sender = getattr(item, 'SenderName', 'Desconhecido')
                try:
                    date_obj = getattr(item, 'ReceivedTime', None)
                except Exception:
                    item = filtered.GetNext()
                    continue
                if not date_obj:
                    item = filtered.GetNext()
                    continue

                date_str = str(date_obj).split('+')[0]
                msg_id = generate_id(subject, date_str, sender)

                # Verifica se este msg_id está na lista de pendentes
                if msg_id not in pending_map:
                    item = filtered.GetNext()
                    continue

                filepath = pending_map[msg_id]

                # Extrai texto dos anexos
                attachments = extract_attachments(item)
                if not attachments:
                    del pending_map[msg_id]
                    item = filtered.GetNext()
                    continue

                anexos_block = ["", "## 📎 Anexos (Textos Extraídos)"]
                for att in attachments:
                    att_name = att.get('name', 'Desconhecido')
                    att_text = AttachmentProcessor.process(att)
                    anexos_block.append(f"### Arquivo: {att_name}")
                    anexos_block.append("```text")
                    if len(att_text) > 3000:
                        anexos_block.append(att_text[:3000] + "\n\n... [Texto do anexo truncado]")
                    elif not att_text.strip():
                        anexos_block.append("[Anexo vazio, ilegível ou OCR não aplicado]")
                    else:
                        anexos_block.append(att_text)
                    anexos_block.append("```")
                    anexos_block.append("")

                try:
                    with open(filepath, 'a', encoding='utf-8') as f:
                        f.write("\n".join(anexos_block))
                    del pending_map[msg_id]
                    updated += 1
                    if updated % 50 == 0:
                        logger.info(f"  >> {updated} MDs atualizados | {len(pending_map)} pendentes restantes")
                except Exception as e:
                    logger.error(f"Erro ao gravar {filepath}: {e}")

            except Exception:
                pass

            item = filtered.GetNext()

    except Exception:
        pass

    # Subpastas
    try:
        for subfolder in folder.Folders:
            if not pending_map:
                return updated
            updated += process_folder(subfolder, pending_map)
    except Exception:
        pass

    return updated

def extract_attachments(item) -> list:
    extracted = []
    try:
        attachments = getattr(item, 'Attachments', None)
        if not attachments:
            return extracted
        for i in range(1, attachments.Count + 1):
            att = attachments.Item(i)
            name = getattr(att, 'FileName', 'anexo.bin')
            fd, temp_path = tempfile.mkstemp(suffix="_" + name)
            os.close(fd)
            try:
                att.SaveAsFile(temp_path)
                with open(temp_path, "rb") as f:
                    data = f.read()
            except Exception:
                data = b""
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            if data:
                extracted.append({"name": name, "mime_type": "application/octet-stream", "data": data})
    except Exception:
        pass
    return extracted

# ── Main ───────────────────────────────────────────────────────────
def main():
    logger.info("=== RETRO-FEED SMART v2 (Frontmatter ID Match) ===")

    # Passo 1: Lê frontmatter de todos os MDs pendentes
    pending_map = build_pending_map()
    if not pending_map:
        logger.info("Todos os MDs já possuem a seção de anexos! Nada a fazer.")
        return

    # Passo 2: Varre o Outlook buscando só e-mails com anexo
    updated = process_outlook(pending_map)

    logger.info("=== RETRO-FEED CONCLUÍDO ===")
    logger.info(f"Arquivos MD atualizados: {updated}")
    logger.info(f"MDs que ficaram sem match no Outlook: {len(pending_map)}")

if __name__ == "__main__":
    main()
