#!/usr/bin/env python3
"""Envia e-mail de notificação com estatísticas da ingestão."""
import os
import sys
import smtplib
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# Config via variáveis de ambiente ou .env
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = "lfbento@gmail.com"
SMTP_PASS = "txhjneknnahrnkjs"
NOTIFY_TO = "lfbento@gmail.com"
DB_PATH = os.getenv("PROGRESS_DB", os.path.join(os.path.dirname(__file__), "data", "db", "md_progress.sqlite"))


def get_stats():
    """Coleta estatísticas do banco de progresso."""
    stats = {"success": 0, "failed": 0, "total_md": 0, "errors": []}
    if not os.path.exists(DB_PATH):
        return stats

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT status, COUNT(*) FROM processed_emails GROUP BY status").fetchall()
        for status, count in rows:
            if status == "SUCCESS":
                stats["success"] = count
            elif status.startswith("FAILED"):
                stats["failed"] += count
                stats["errors"].append(f"{status}: {count}")

    # conta MDs na pasta de saída
    md_dir = os.getenv("MD_OUTPUT_DIR", "/home/bento/obsidian_v2")
    if os.path.isdir(md_dir):
        stats["total_md"] = sum(1 for f in os.listdir(md_dir) if f.endswith(".md"))

    return stats


def send_email(stats, elapsed_seconds):
    """Envia e-mail de notificação."""
    if not SMTP_PASS:
        print("AVISO: SMTP_PASS não configurado. E-mail não enviado.")
        print(f"Stats: {stats}")
        return False

    elapsed = str(timedelta(seconds=int(elapsed_seconds)))
    rate = stats["success"] / max(elapsed_seconds / 60, 1)

    body = f"""
Ingestão de e-mails concluída — {datetime.now().strftime('%d/%m/%Y %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ESTATÍSTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Sucesso:     {stats['success']}
❌ Falhas:      {stats['failed']}
📄 MDs total:   {stats['total_md']}
⏱️  Tempo:       {elapsed}
📈 Taxa:        {rate:.1f} emails/minuto

{'━' * 40}
Erros: {', '.join(stats['errors']) if stats['errors'] else 'Nenhum'}

Pipeline: app-outlook-novo (Docling GPU + EasyOCR GPU)
Servidor: {os.uname().nodename}
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_TO
    msg["Subject"] = f"📧 Ingestão concluída — {stats['success']} emails processados"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"E-mail enviado para {NOTIFY_TO}")
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


if __name__ == "__main__":
    elapsed = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    stats = get_stats()
    send_email(stats, elapsed)
