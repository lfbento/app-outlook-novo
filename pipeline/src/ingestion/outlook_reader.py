import os
import sqlite3
import datetime
import hashlib
import tempfile
import logging
from typing import Dict, Any, Generator

import win32com.client
import pythoncom

logger = logging.getLogger(__name__)

class ProgressDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_emails (
                    id TEXT PRIMARY KEY,
                    subject TEXT,
                    date TEXT,
                    status TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def is_processed(self, email_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Qualquer status cadastrado (SUCCESS, QUEUED, FAILED) significa que já tentamos enfileirar
            cursor.execute('SELECT 1 FROM processed_emails WHERE id = ?', (email_id,))
            return cursor.fetchone() is not None

    def mark_processed(self, email_id: str, subject: str, date: str, status: str = "SUCCESS"):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO processed_emails (id, subject, date, status)
                VALUES (?, ?, ?, ?)
            ''', (email_id, subject, date, status))
            conn.commit()

    def get_latest_processed_date(self) -> str:
        """Busca a maior data entre os e-mails processados."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(date) FROM processed_emails WHERE status IN ("SUCCESS", "QUEUED")')
            row = cursor.fetchone()
            return row[0] if row and row[0] else None


class OutlookIngestor:
    def __init__(self, target_accounts: list, db_path: str = "data/db/progress.sqlite"):
        """
        Lê e-mails nativamente do aplicativo Microsoft Outlook via COM (win32com).
        """
        self.target_accounts = target_accounts
        self.db = ProgressDB(db_path)

    def _generate_id(self, subject: str, date_str: str, sender: str) -> str:
        raw = f"{subject}_{date_str}_{sender}".encode('utf-8', errors='ignore')
        return hashlib.md5(raw).hexdigest()

    def process_emails(self, test_mode: bool = False, limit_per_folder: int = 0, since_date: str = None) -> Generator[Dict[str, Any], None, None]:
        # Necessário para threads/generators utilizando COM no Windows
        pythoncom.CoInitialize()

        # Converte string de data para objeto datetime se fornecido
        cutoff_date = None
        if since_date:
            try:
                # Suporta YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS
                if len(since_date) > 10:
                    cutoff_date = datetime.datetime.strptime(since_date.split('.')[0], "%Y-%m-%d %H:%M:%S")
                else:
                    cutoff_date = datetime.datetime.strptime(since_date, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Formato de data 'since_date' inválido: {since_date}.")
        
        try:
            outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            
            for account_name in self.target_accounts:
                logger.info(f"Procurando conta: {account_name}")
                account_folder = None
                
                # Encontra a root folder da conta
                for i in range(1, outlook.Folders.Count + 1):
                    folder = outlook.Folders.Item(i)
                    if folder.Name == account_name:
                        account_folder = folder
                        break
                
                if not account_folder:
                    logger.warning(f"Conta '{account_name}' não encontrada no Outlook. Pulando.")
                    continue
                    
                logger.info(f"Lendo e-mails da conta: {account_name}")
                yield from self._process_folder(account_folder, account_name, test_mode, limit_per_folder, cutoff_date)
                
        finally:
            pythoncom.CoUninitialize()

    def _process_folder(self, folder, account_name: str, test_mode: bool, limit_per_folder: int, cutoff_date: datetime.datetime = None) -> Generator[Dict[str, Any], None, None]:
        folder_name = folder.Name.lower()
        
        # Filtro: Apenas Caixa de Entrada (Inbox) e Itens Enviados (Sent Items)
        allowed_folders = ['caixa de entrada', 'inbox', 'itens enviados', 'sent items']
        is_allowed = any(allowed in folder_name for allowed in allowed_folders) or folder_name == account_name.lower()
        
        if not is_allowed:
            logger.debug(f"Ignorando pasta {folder.Name}")
            return

        try:
            items = folder.Items
            # Para otimizar a iteração em coleções COM
            items.Sort("[ReceivedTime]", True) # Mais recentes primeiro
            
            folder_processed_count = 0
            
            # Filtro básico por tipo (excluir reuniões etc.) -> 'MailItem' object class é 43
            for item in items:
                try:
                    if getattr(item, 'Class', 0) != 43: # 43 = olMail
                        continue
                    
                    if limit_per_folder > 0 and folder_processed_count >= limit_per_folder:
                        break
                        
                    subject = getattr(item, 'Subject', '') or "Sem Assunto"
                    sender = getattr(item, 'SenderName', 'Desconhecido')
                    
                    try:
                        date_obj = getattr(item, 'ReceivedTime', None)
                    except Exception:
                        date_obj = datetime.datetime.now()
                        
                    if not date_obj:
                        date_obj = datetime.datetime.now()
                        
                    # Converter PyTime para str
                    date_str = str(date_obj).split('+')[0] # Remove timezone extra as vezes retornado pelo pywintypes

                    # Filtro de Data de Corte (Cutoff)
                    if cutoff_date and date_obj:
                        # Se o e-mail for mais antigo que o cutoff, paramos esta pasta (já que estão ordenados por data DESC)
                        naive_date_obj = date_obj.replace(tzinfo=None)
                        if naive_date_obj < cutoff_date:
                            logger.info(f"Atingido limite de data na pasta {folder.Name}. Pulando e-mails antigos.")
                            break
                    
                    msg_id = self._generate_id(subject, date_str, sender)

                    if self.db.is_processed(msg_id):
                        continue

                    # Extração de Thread
                    conversation_topic = getattr(item, 'ConversationTopic', '') or ''
                    conversation_index = getattr(item, 'ConversationIndex', '') or ''
                    # Os primeiros 22 bytes (44 chars em hexa ou equivalente) representam a conversa raiz
                    # Vamos usar os primeiros 22 bytes para criar o ID da thread
                    thread_id = ""
                    if conversation_index:
                        # O format do index pode variar, mas os bytes iniciais são a chave
                        thread_id = hashlib.md5(str(conversation_index)[:44].encode('utf-8', errors='ignore')).hexdigest()

                    body = getattr(item, 'Body', "")
                    attachments = self._extract_attachments(item, msg_id)

                    yield {
                        "id": msg_id,
                        "file_path": f"{account_name}/{folder.Name}/{subject[:20]}",
                        "subject": subject,
                        "sender": sender,
                        "to": getattr(item, 'To', "Desconhecido"),
                        "date": date_str,
                        "body": body,
                        "attachments": attachments,
                        "conversation_topic": conversation_topic,
                        "thread_id": thread_id
                    }
                    
                    folder_processed_count += 1
                    
                except Exception as e:
                    logger.debug(f"Erro lendo mensagem específica em {folder.Name}: {e}")
                    
        except Exception as e:
            logger.error(f"Erro ao varrer a pasta {folder.Name}: {e}")

        # Entra Subpastas Recursivamente
        try:
            for subfolder in folder.Folders:
                yield from self._process_folder(subfolder, account_name, test_mode, limit_per_folder, cutoff_date)
        except Exception:
            pass

    def _extract_attachments(self, item, msg_id: str) -> list:
        extracted = []
        try:
            attachments = getattr(item, 'Attachments', None)
            if not attachments:
                return extracted
                
            tmp_dir = os.path.join(os.path.dirname(os.path.abspath(self.db.db_path)), "..", "extractions", "tmp_bin")
            os.makedirs(tmp_dir, exist_ok=True)
            
            for i in range(1, attachments.Count + 1):
                att = attachments.Item(i)
                name = getattr(att, 'FileName', 'anexo_desconhecido.bin')
                
                safe_name = f"{msg_id}_{i}_{name}"
                safe_name = "".join([c for c in safe_name if c.isalpha() or c.isdigit() or c in (' ', '.', '_', '-')]).rstrip()
                temp_path = os.path.abspath(os.path.join(tmp_dir, safe_name))
                
                saved_successfully = False
                try:
                    att.SaveAsFile(temp_path)
                    saved_successfully = True
                except Exception as e:
                    logger.debug(f"Erro salvando anexo {name}: {e}")

                if saved_successfully and os.path.exists(temp_path):
                    extracted.append({
                        "name": name,
                        "mime_type": "application/octet-stream", # Não vem fácil no win32com
                        "file_path": temp_path
                    })
        except Exception as e:
            logger.debug(f"Falha enumerando anexos da mensagem MSAPI: {e}")
            
        return extracted
