"""Driver batch: varre .msg, converte corpo+anexos para Markdown (GPU)."""
import argparse
import glob
import logging
import os
import sqlite3
from concurrent.futures import ProcessPoolExecutor, as_completed

import torch

from config import EMAIL_SOURCE_DIR, MD_OUTPUT_DIR, PROGRESS_DB, USE_GPU
from src.ingestion.msg_reader import read_msg
from src.ingestion.attachment_processor import AttachmentProcessor
from src.markdown.email_formatter import EmailFormatter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("convert_to_md")


def init_db():
    os.makedirs(os.path.dirname(PROGRESS_DB), exist_ok=True)
    with sqlite3.connect(PROGRESS_DB) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS processed_emails ("
            " id TEXT PRIMARY KEY, status TEXT NOT NULL )"
        )


def is_done(msg_id: str) -> bool:
    with sqlite3.connect(PROGRESS_DB) as conn:
        return conn.execute(
            "SELECT 1 FROM processed_emails WHERE id=? AND status='SUCCESS'",
            (msg_id,),
        ).fetchone() is not None


def mark(msg_id: str, status: str):
    with sqlite3.connect(PROGRESS_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO processed_emails(id, status) VALUES(?, ?)",
            (msg_id, status),
        )


def _convert_one(path: str) -> str:
    """Lê .msg + converte anexos (MarkItDown/Docling GPU/EasyOCR GPU)."""
    email = read_msg(path)
    texts = []
    for att in email["attachments"]:
        try:
            texts.append(AttachmentProcessor.process(att))
        except Exception as e:
            texts.append(f"[erro: {e}]")
    fmt = EmailFormatter(output_dir=MD_OUTPUT_DIR)
    out = fmt.format_email(email, texts)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=EMAIL_SOURCE_DIR)
    ap.add_argument("--out", default=MD_OUTPUT_DIR)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    init_db()
    logger.info("GPU disponível: %s", torch.cuda.is_available())
    files = sorted(glob.glob(os.path.join(args.source, "**", "*.msg"), recursive=True))

    # retomada: pular já processados com sucesso (por path do arquivo como id)
    todo = [f for f in files if not is_done(os.path.basename(f))]
    if args.limit:
        todo = todo[: args.limit]
    logger.info("Total .msg: %d | a converter: %d", len(files), len(todo))

    # GPU: serializa naturalmente (1 worker); CPU: paralelo com nproc-1.
    # ProcessPoolExecutor com workers > 1 permite MarkItDown/parsing em paralelo,
    # mas Docling/EasyOCR competem pela GPU de 8GB. Usamos pool moderado.
    max_workers = max(1, min(4, (os.cpu_count() or 2) - 1))
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_convert_one, f): f for f in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            f = futs[fut]
            try:
                out = fut.result()
                mark(os.path.basename(f), "SUCCESS")
                if i % 20 == 0:
                    logger.info("Progresso: %d/%d", i, len(todo))
            except Exception as e:
                logger.error("Falha %s: %s", f, e)
                mark(os.path.basename(f), f"FAILED: {e}")

    logger.info("Concluído.")


if __name__ == "__main__":
    main()
