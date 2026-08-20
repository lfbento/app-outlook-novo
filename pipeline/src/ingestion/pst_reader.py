import os
import sqlite3
import datetime
import hashlib
import tempfile
import logging
from typing import Dict, Any, Generator

try:
    from aspose.email.storage.pst import PersonalStorage
except ImportError:
    PersonalStorage = None

logger = logging.getLogger(__name__)

class ProgressDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        # Garante que o diretório exista
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
            cursor.execute('SELECT 1 FROM processed_emails WHERE id = ? AND status = "SUCCESS"', (email_id,))
            return cursor.fetchone() is not None

    def mark_processed(self, email_id: str, subject: str, date: str, status: str = "SUCCESS"):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO processed_emails (id, subject, date, status)
                VALUES (?, ?, ?, ?)
            ''', (email_id, subject, date, status))
            conn.commit()


class EmailIngestor:
    def __init__(self, pst_path: str, db_path: str = "data/db/progress.sqlite"):
        """
        Lê diretamente o .PST usando a biblioteca corporativa Aspose.Email sem abrir todo o arquivo na memória.
        """
        self.pst_path = pst_path
        self.db = ProgressDB(db_path)

    def _generate_id(self, subject: str, date_str: str, sender: str) -> str:
        """Gera um ID único baseado na mensagem"""
        raw = f"{subject}_{date_str}_{sender}".encode('utf-8', errors='ignore')
        return hashlib.md5(raw).hexdigest()

    def _is_year_2026(self, email_date: datetime.datetime) -> bool:
        if not email_date:
            return False
        try:
            # Torna timezone-naive
            email_date = email_date.replace(tzinfo=None)
            return email_date.year == 2026
        except Exception:
            return False

    def process_pst(self, test_mode: bool = True) -> Generator[Dict[str, Any], None, None]:
        """
        Inicia a navegação e geração de E-mails do arquivo PST.
        """
        if PersonalStorage is None:
            logger.error("A biblioteca 'aspose-email-for-python-via-net' não está instalada.")
            return

        if not os.path.exists(self.pst_path):
            logger.error(f"PST não encontrado em: {self.pst_path}")
            return

        logger.info(f"Montando e validando header PST: {self.pst_path}")
        pst = PersonalStorage.from_file(self.pst_path)
        
        try:
            # Varre o root e suas subpastas de forma recursiva (Generator para economia de Ram)
            yield from self._process_folder(pst, pst.root_folder, test_mode)
        finally:
            # O .NET/Aspose em Python 3 nem sempre expõe dispose, tentamos para segurança
            if hasattr(pst, 'dispose'):
                try:
                    pst.dispose()
                except Exception:
                    pass

    def _process_folder(self, pst, folder, test_mode: bool) -> Generator[Dict[str, Any], None, None]:
        if folder is None:
            return

        folder_name = getattr(folder, 'display_name', 'Unknown').lower()
        
        # Filtro de pastas ignoradas: Lixeira, Spam, Rascunhos
        ignored_folders = ['itens excluídos', 'deleted items', 'lixo eletrônico', 'junk e-mail', 'rascunhos', 'drafts', 'spam']
        for ignored in ignored_folders:
            if ignored in folder_name:
                logger.debug(f"Ignorando pasta {folder_name}")
                return

        try:
            # Pega as mensagens do diretório atual
            for msg_info in folder.enumerate_messages():
                # Faz extração rápida dos metadados básicos na folha do MAPI
                subject = msg_info.subject or "Sem Assunto"
                sender = msg_info.sender_representative_name or "Desconhecido"
                
                # Tenta puxar a mensagem inteira e os anexos (pesado, logo filtramos data aqui embaixo)
                try:
                    msg = pst.extract_message(msg_info)
                except Exception as e:
                    logger.warning(f"Erro extraindo MapiMessage '{subject}': {e}")
                    continue

                if not msg:
                    continue

                # Pega e valida a data
                date_obj = getattr(msg, 'client_submit_time', None) or getattr(msg, 'delivery_time', None)
                if not date_obj:
                    date_obj = datetime.datetime.now()
                
                date_str = str(date_obj)

                # Verifica Filtro Especial (Apenas Ano 2026) ANTES de ler o body ou anexos salvando processamento longo
                if test_mode and not self._is_year_2026(date_obj):
                    continue

                msg_id = self._generate_id(subject, date_str, sender)

                # Verifica Banco de Dados para retomar progresso
                if self.db.is_processed(msg_id):
                    continue
                
                body = getattr(msg, 'body', "")
                if not body:
                    body = getattr(msg, 'body_html', "")
                
                attachments = self._extract_attachments(msg)

                yield {
                    "id": msg_id,
                    "file_path": f"{folder.display_name}/{subject[:20]}",
                    "subject": subject,
                    "sender": sender,
                    "to": getattr(msg, 'display_to', "Desconhecido"),
                    "date": date_str,
                    "body": body,
                    "attachments": attachments
                }
        except Exception as e:
            logger.error(f"Erro ao varrer a pasta {getattr(folder, 'display_name', 'Unknown')}: {e}")

        # Entra Subpastas Recursivamente
        try:
            for subfolder in folder.get_sub_folders():
                yield from self._process_folder(pst, subfolder, test_mode)
        except Exception as e:
            pass

    def _extract_attachments(self, msg) -> list:
        """Extrai anexos para arquivos temporários no SO e os puxa de volta como base bytearray/bytes para descarregar o Stream COM."""
        extracted = []
        try:
            if not getattr(msg, 'attachments', None): return extracted
            
            for att in msg.attachments:
                # Aspose as vezes quebra o file_name, priorizamos o longo
                name = getattr(att, 'long_file_name', None) or getattr(att, 'display_name', None) or getattr(att, 'file_name', 'anexo_desconhecido.bin')
                
                fd, temp_path = tempfile.mkstemp()
                os.close(fd)
                try:
                    # Aspose salva no disco usando a interface COM .NET por baixo
                    att.save(temp_path)
                    with open(temp_path, "rb") as f:
                        data = f.read()
                except Exception as e:
                    logger.warning(f"Erro lendo/salvando anexo {name}: {e}")
                    data = b""
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                if data:
                    extracted.append({
                        "name": name,
                        "mime_type": getattr(att, 'mime_tag', 'application/octet-stream'),
                        "data": data
                    })
        except Exception as e:
            logger.error(f"Falha enumerando anexos da mensagem MSAPI: {e}")
            
        return extracted
