"""Leitor de arquivos .msg (Outlook MSG / OLE2) — substituto do outlook_reader COM."""
import os
import hashlib
import logging
from typing import Any, Dict, List

from extract_msg import Message

logger = logging.getLogger(__name__)


def _safe(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            value = value.decode("latin-1", errors="replace")
    return str(value or "")


def read_msg(path: str) -> Dict[str, Any]:
    """Lê um .msg e devolve um dict estruturado com anexos em bytes."""
    with Message(path) as msg:
        subject = _safe(msg.subject) or "Sem Assunto"
        date = _safe(msg.date)
        sender = _safe(msg.sender)
        to = _safe(msg.to)
        cc = _safe(msg.cc)
        body_html = _safe(msg.htmlBody)
        body_text = _safe(msg.body)

        attachments: List[Dict[str, Any]] = []
        for att in msg.attachments:
            try:
                name = att.longFilename or att.shortFilename or "anexo.bin"
                data = att.data
                if data:
                    attachments.append({"name": name, "data": data})
            except Exception as e:
                logger.warning("Falha ao ler anexo de %s: %s", path, e)

    # id estável (dedupe/retomada)
    raw = f"{subject}_{date}_{sender}".encode("utf-8", errors="ignore")
    msg_id = hashlib.md5(raw).hexdigest()

    account = os.path.basename(os.path.dirname(os.path.dirname(path)))
    folder = os.path.basename(os.path.dirname(path))
    direction = "ENVIADO" if "Itens Enviados" in folder else "RECEBIDO"

    return {
        "id": msg_id,
        "account": account,
        "folder": folder,
        "subject": subject,
        "sender": sender,
        "sender_email": sender,
        "to": to,
        "cc": cc,
        "date": date,
        "direction": direction,
        "body_html": body_html,
        "body_text": body_text,
        "attachments": attachments,
    }
