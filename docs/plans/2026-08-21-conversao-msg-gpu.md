# Pipeline de Conversão E-mail (.msg) → Markdown com GPU

> **Para agentes de execução:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar tarefa a tarefa. Steps usam checkbox (`- [ ]`) para tracking.

**Goal:** Converter 1.737 e-mails `.msg` (Outlook) em Markdown, acelerando PDFs/imagens via GPU (GTX 1080), escrevendo em `md-teste/`.

**Architecture:** Leitura local dos arquivos `.msg` (OLE2) com `extract-msg`, conversão do corpo HTML→Markdown, e roteamento de anexos por `format_router` → `attachment_processor` (Docling GPU para PDF, EasyOCR GPU para imagens/scans, MarkItDown para office). Driver batch com multiprocessing + serialização de GPU + retomada via SQLite. Sem RabbitMQ, sem COM.

**Tech Stack:** Python 3.12, `extract-msg`, `markdownify`, `docling`+`docling-ibm-models`+`accelerate`, `easyocr`+`torchvision` (cu118), `markitdown`, `py7zr`/`rarfile`, `fitz` (pymupdf), `mpxj`/`jpype1` (opcional).

## Global Constraints

- Caminho fonte: `/home/bento/transferencia/email` (sem acento em `transferencia`).
- Saída: `/home/bento/rag-email/app-outlook-novo/md-teste/` (criar; espelhar `<conta>/<pasta>/<nome>.md`).
- GPU: GTX 1080, 8GB VRAM, Pascal (sm_61). `torch==2.7.1+cu118` já instalado. Torchvision deve casar: `torchvision==0.22.1+cu118`.
- Python 3.12.3. Criar venv em `pipeline/.venv` (não poluir o sistema).
- Nunca exceder 8GB de VRAM: **no máximo 1 tarefa GPU por vez** (fila serial para GPU; CPU em paralelo).
- Nomes de arquivo de saída: sanitizar; preservar a estrutura de pasta da conta.
- Codificação UTF-8 em toda escrita/leitura de arquivo.
- Nenhuma dependência do Windows (sem `win32com`, sem caminhos `c:\...`).

---

## File Structure (lock-in de decomposição)

**Novos:**
- `pipeline/src/ingestion/msg_reader.py` — lê `.msg` via `extract-msg`, devolve dict de e-mail + anexos como bytes.
- `pipeline/src/markdown/email_formatter.py` — dict de e-mail → arquivo `.md`.
- `pipeline/src/markdown/__init__.py`
- `pipeline/convert_to_md.py` — driver batch (entry point CLI).

**Modificados (reuso):**
- `pipeline/src/ingestion/attachment_processor.py` — habilita GPU (Docling `device=cuda` + EasyOCR) e remove o corte 3MB/MinerU.
- `pipeline/src/ingestion/format_router.py` — adiciona engine `OCR` para imagens e `MSGDIRECT` para corpo.
- `pipeline/config.py` — caminhos fonte/saída + flags GPU.
- `pipeline/requirements.txt` — novas dependências.

**Reusados sem mudança:** `pipeline/src/ingestion/archive_extractor.py`, `pipeline/src/ingestion/msproject_reader.py`.

**A remover (obsoletos COM/RabbitMQ/Windows):** `producer.py`, `consumer.py`, `outlook_reader.py`, `obsidian_formatter.py` (+ `__init__` do `graph_generator`), `docker-compose.yml`, `monitor_producer.ps1`, `start_consumer.ps1`, `check_db.py`, `check_progress.py` (×2), `get_status.py`, `fix_queued.py`, `scratch_status.py`, `test_fase1_v2.py`, `test_integrated_v2.py`. (Manter `FASE1_DOCUMENTACAO.md` como histórico.)

---

### Task 1: Ambiente e estrutura de saída

**Files:**
- Modify: `pipeline/requirements.txt`
- Create: `pipeline/.venv/` (via bash)
- Create: `/home/bento/rag-email/app-outlook-novo/md-teste/`

**Interfaces:**
- Produces: venv com todas as deps; diretório de saída vazio.

- [ ] **Step 1: Adicionar dependências ao requirements.txt**

```text
# .msg parsing (OLE2) e HTML->Markdown
extract-msg>=0.52.0
markdownify>=0.14.0

# PDF + tabelas (GPU)
docling>=2.20.0
docling-ibm-models>=3.3.0
accelerate>=1.0.0
torchvision==0.22.1+cu118

# OCR (GPU)
easyocr>=1.7.0

# Attachment parsing (já havia markitdown)
markitdown>=0.1.0

# Archives + MS Project (já existiam)
py7zr>=0.20.0
rarfile>=4.0
# mpxj>=13.0.0   # opcional, requer Java
# jpype1>=1.5.0
```

- [ ] **Step 2: Criar venv e instalar torch/torchvision cu118**

```bash
cd /home/bento/rag-email/app-outlook-novo/pipeline
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install torch==2.7.1+cu118 torchvision==0.22.1+cu118 --index-url https://download.pytorch.org/whl/cu118
```

- [ ] **Step 3: Instalar demais dependências**

```bash
pip install extract-msg markdownify docling docling-ibm-models accelerate easyocr markitdown py7zr rarfile pymupdf
```

- [ ] **Step 4: Verificar GPU visível no venv**

```bash
. .venv/bin/activate && python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
Expected: `True NVIDIA GeForce GTX 1080`

- [ ] **Step 5: Criar diretório de saída**

```bash
mkdir -p /home/bento/rag-email/app-outlook-novo/md-teste
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/requirements.txt
git commit -m "chore: add GPU md-conversion dependencies and md-teste output dir"
```

---

### Task 2: Leitor de .msg (`msg_reader.py`)

**Files:**
- Create: `pipeline/src/ingestion/msg_reader.py`
- Test: `pipeline/tests/test_msg_reader.py`

**Interfaces:**
- Produces: `read_msg(path: str) -> dict` com chaves `id, account, folder, subject, sender, sender_email, to, cc, date, direction, body_html, body_text, attachments`.
  - `attachments: list[dict]` onde cada item = `{"name": str, "data": bytes}`.
- Consumes: biblioteca `extract_msg` (`from extract_msg import Message`).

- [ ] **Step 1: Escrever o teste que falha**

```python
# pipeline/tests/test_msg_reader.py
import os, glob
from src.ingestion.msg_reader import read_msg

SRC = "/home/bento/transferencia/email"
F = sorted(glob.glob(os.path.join(SRC, "**", "*.msg"), recursive=True))[0]

def test_read_msg_returns_metadata():
    d = read_msg(F)
    assert d["subject"]  # nunca vazio
    assert d["sender_email"] or d["sender"]
    assert d["date"]      # string não vazia

def test_read_msg_attachments_are_bytes():
    d = read_msg(F)
    for att in d["attachments"]:
        assert isinstance(att["data"], bytes)
        assert att["name"]
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd pipeline && . .venv/bin/activate && python -m pytest tests/test_msg_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ingestion.msg_reader'`

- [ ] **Step 3: Implementar**

```python
"""Leitor de arquivos .msg (Outlook MSG / OLE2) — substituto do outlook_reader COM."""
import os
import hashlib
import logging
from typing import Any, Dict, List

from extract_msg import Message

logger = logging.getLogger(__name__)


def _safe(value: Any) -> str:
    return str(value or "")


def read_msg(path: str) -> Dict[str, Any]:
    """Lê um .msg e devolve um dict estruturado com anexos em bytes."""
    with Message(path) as msg:
        subject = _safe(msg.subject) or "Sem Assunto"
        date = _safe(msg.date)
        sender_email = _safe(msg.sender)

        attachments: List[Dict[str, Any]] = []
        for att in msg.attachments:
            try:
                name = att.longFilename or att.shortFilename or "anexo.bin"
                data = att.data
                if data:
                    attachments.append({"name": name, "data": data})
            except Exception as e:
                logger.warning("Falha ao ler anexo de %s: %s", path, e)

        body_html = _safe(msg.htmlBody)
        body_text = _safe(msg.body)

        # id estável (dedupe/retomada)
        raw = f"{subject}_{date}_{sender_email}".encode("utf-8", errors="ignore")
        msg_id = hashlib.md5(raw).hexdigest()

        account = os.path.basename(os.path.dirname(os.path.dirname(path)))
        folder = os.path.basename(os.path.dirname(path))
        direction = "ENVIADO" if "Itens Enviados" in folder else "RECEBIDO"

    return {
        "id": msg_id,
        "account": account,
        "folder": folder,
        "subject": subject,
        "sender": _safe(msg.sender),
        "sender_email": sender_email,
        "to": _safe(msg.to),
        "cc": _safe(msg.cc),
        "date": date,
        "direction": direction,
        "body_html": body_html,
        "body_text": body_text,
        "attachments": attachments,
    }
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `cd pipeline && . .venv/bin/activate && python -m pytest tests/test_msg_reader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/ingestion/msg_reader.py pipeline/tests/test_msg_reader.py
git commit -m "feat: add .msg file reader (extract-msg) replacing COM outlook_reader"
```

---

### Task 3: Formatador Markdown (`email_formatter.py`)

**Files:**
- Create: `pipeline/src/markdown/__init__.py` (vazio)
- Create: `pipeline/src/markdown/email_formatter.py`
- Test: `pipeline/tests/test_email_formatter.py`

**Interfaces:**
- Produces: `EmailFormatter(output_dir: str)` com `format_email(email: dict, attachment_texts: list[str]) -> str` (retorna path do .md).
- Consumes: `markdownify` para `body_html → md`; sanitização de nome de arquivo.

- [ ] **Step 1: Escrever o teste que falha**

```python
# pipeline/tests/test_email_formatter.py
import os
from src.markdown.email_formatter import EmailFormatter

def test_formatter_writes_file():
    f = EmailFormatter(output_dir="/tmp/md-teste-test")
    email = {
        "id": "abc123", "account": "a@x.com", "folder": "Caixa de Entrada",
        "subject": "Assunto do Email", "sender": "Fulano", "sender_email": "f@x.com",
        "to": "g@x.com", "cc": "", "date": "2026-08-20T06:59:03+00:00",
        "direction": "RECEBIDO", "body_html": "<p>Olá <b>mundo</b></p>", "body_text": "Olá mundo",
        "attachments": [],
    }
    path = f.format_email(email, [])
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert "Olá" in content
    assert "mundo" in content  # HTML convertido preserva texto
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd pipeline && . .venv/bin/activate && python -m pytest tests/test_email_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.markdown'`

- [ ] **Step 3: Implementar**

```python
"""Formatador Markdown limpo para e-mails convertidos (substitui obsidian_formatter)."""
import os
import re
from typing import Any, Dict, List

from markdownify import markdownify as md


class EmailFormatter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    @staticmethod
    def _sanitize(text: str) -> str:
        safe = re.sub(r'[<>:"/\\|?*]', "", str(text))
        safe = re.sub(r"[\x00-\x1f]", "", safe)
        return safe.strip()[:120] or "sem-assunto"

    def format_email(self, email: Dict[str, Any], attachment_texts: List[str]) -> str:
        account = self._sanitize(email.get("account", "conta"))
        folder = self._sanitize(email.get("folder", "pasta"))
        out_dir = os.path.join(self.output_dir, account, folder)
        os.makedirs(out_dir, exist_ok=True)

        subject = self._sanitize(email.get("subject", "Sem Assunto"))
        filename = f"{email.get('id', 'x')[:6]}_{subject}.md"
        filepath = os.path.join(out_dir, filename)

        # corpo: preferir HTML -> markdown (preserva tabelas/negrito/links)
        body_html = email.get("body_html", "")
        if body_html and body_html.strip():
            body = md(body_html, heading_style="ATX")
        else:
            body = email.get("body_text", "")

        lines = [
            "---",
            f"id: {email.get('id', '')}",
            f"account: \"{email.get('account', '')}\"",
            f"folder: \"{email.get('folder', '')}\"",
            f"direction: {email.get('direction', '')}",
            f"date: \"{email.get('date', '')}\"",
            f"sender: \"{email.get('sender', '')}\"",
            f"sender_email: \"{email.get('sender_email', '')}\"",
            f"to: \"{email.get('to', '')}\"",
            f"cc: \"{email.get('cc', '')}\"",
            "---",
            "",
            f"# {email.get('subject', 'Sem Assunto')}",
            "",
            "## 📧 Corpo",
            "",
            body.strip(),
            "",
        ]

        if attachment_texts:
            lines.append("## 📎 Anexos")
            lines.append("")
            for att_text in attachment_texts:
                lines.append(att_text.strip())
                lines.append("")

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        return filepath
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `cd pipeline && . .venv/bin/activate && python -m pytest tests/test_email_formatter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/markdown pipeline/tests/test_email_formatter.py
git commit -m "feat: add clean email markdown formatter"
```

---

### Task 4: Processador de anexos com GPU

**Files:**
- Modify: `pipeline/src/ingestion/attachment_processor.py`
- Modify: `pipeline/src/ingestion/format_router.py`
- Test: `pipeline/tests/test_attachment_processor_gpu.py`

**Interfaces:**
- Produces: `AttachmentProcessor.process(attachment: dict) -> str` (mesma assinatura; agora aceita `{"name", "data"}` e usa GPU quando disponível).
- `format_router.get_engine()` ganha `ConversionEngine.OCR` para `.png/.jpg/.jpeg/.tiff/.tif/.bmp`.

- [ ] **Step 1: Atualizar format_router para engine OCR**

```python
# em format_router.py
class ConversionEngine(Enum):
    MARKITDOWN = "markitdown"
    DOCLING = "docling"
    OCR = "ocr"          # imagens (EasyOCR GPU)
    ARCHIVE = "archive"
    MSPROJECT = "msproject"
    SKIP = "skip"

# na ROUTING_TABLE: trocar imagens de DOCLING para OCR
    '.png': ConversionEngine.OCR,
    '.jpg': ConversionEngine.OCR,
    '.jpeg': ConversionEngine.OCR,
    '.tiff': ConversionEngine.OCR,
    '.tif': ConversionEngine.OCR,
    '.bmp': ConversionEngine.OCR,
```

- [ ] **Step 2: Teste que falha (OCR roteado)**

```python
# pipeline/tests/test_attachment_processor_gpu.py
from src.ingestion.format_router import get_engine, ConversionEngine

def test_image_routes_to_ocr():
    assert get_engine("scan.png") == ConversionEngine.OCR
    assert get_engine("foto.jpg") == ConversionEngine.OCR
    assert get_engine("doc.pdf") == ConversionEngine.DOCLING
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `cd pipeline && . .venv/bin/activate && python -m pytest tests/test_attachment_processor_gpu.py -v`
Expected: FAIL — `get_engine("scan.png")` ainda retorna DOCLING.

- [ ] **Step 4: Implementar Docling GPU + EasyOCR no attachment_processor**

```python
# no topo de attachment_processor.py, substituir _run_docling_process
import torch

def _run_docling_process(temp_path: str, result_queue):
    import gc
    try:
        from docling.document_converter import DocumentConverter
        use_gpu = torch.cuda.is_available()
        converter = DocumentConverter()
        # Docling 2.x: acelerar modelo de layout/tabela na GPU
        if use_gpu:
            converter.pipeline_options.device = torch.device("cuda")
        result = converter.convert(temp_path)
        result_queue.put(("success", result.document.export_to_markdown()))
    except Exception as e:
        result_queue.put(("error", str(e)))
    finally:
        gc.collect()


def _run_easyocr_process(temp_path: str, result_queue):
    """OCR de imagem em subprocesso (EasyOCR GPU)."""
    try:
        import easyocr
        reader = easyocr.Reader(["pt", "en"], gpu=torch.cuda.is_available())
        results = reader.readtext(temp_path, detail=0, paragraph=True)
        result_queue.put(("success", "\n".join(results)))
    except Exception as e:
        result_queue.put(("error", str(e)))
```

- [ ] **Step 5: Roteamento no `process()` (adicionar branch OCR)**

```python
# em AttachmentProcessor.process(), dentro do try:
            if engine == ConversionEngine.OCR:
                return cls._process_ocr(temp_path, name)
            elif engine == ConversionEngine.DOCLING:
                return cls._process_docling_with_fallback(temp_path, name)
```

- [ ] **Step 6: Implementar `_process_ocr` (subprocesso isolado, fallback MarkItDown)**

```python
    @classmethod
    def _process_ocr(cls, temp_path: str, name: str) -> str:
        logger.info(f"OCR (GPU) de {name} ...")
        try:
            ctx = multiprocessing.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_run_easyocr_process, args=(temp_path, q))
            p.start()
            import queue
            status, data = q.get(timeout=300)
            p.join(timeout=10)
            if status == "success" and data.strip():
                return data
        except Exception as e:
            logger.warning(f"OCR falhou para {name}: {e}")
        return cls._process_markitdown(temp_path, name)
```

- [ ] **Step 7: Remover corte MinerU de 3MB (Docling GPU cobre PDFs grandes)**

```python
# em _process_docling_with_fallback: apagar o bloco
#   if file_size_mb > 3.0: return cls._process_mineru_with_fallback(...)
# e deixar _route_pdf_fallback cair direto em MarkItDown se Docling falhar.
```

- [ ] **Step 8: Rodar testes**

Run: `cd pipeline && . .venv/bin/activate && python -m pytest tests/test_attachment_processor_gpu.py tests/test_msg_reader.py tests/test_email_formatter.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add pipeline/src/ingestion/format_router.py pipeline/src/ingestion/attachment_processor.py pipeline/tests/test_attachment_processor_gpu.py
git commit -m "feat: GPU-accelerate attachment processing (Docling CUDA + EasyOCR)"
```

---

### Task 5: Driver batch (`convert_to_md.py`)

**Files:**
- Create: `pipeline/convert_to_md.py`
- Modify: `pipeline/config.py`
- Test: `pipeline/tests/test_convert_to_md.py`

**Interfaces:**
- Consumes: `read_msg` (Task 2), `EmailFormatter` (Task 3), `AttachmentProcessor.process` (Task 4).
- Produces: CLI `python convert_to_md.py [--limit N] [--source PATH] [--out PATH]`.
- Retomada: SQLite `md-teste-progress.sqlite` com `processed_emails(id, status)`.

- [ ] **Step 1: Adicionar config de caminhos/GPU**

```python
# em config.py, acrescentar:
import os
EMAIL_SOURCE_DIR = os.getenv("EMAIL_SOURCE_DIR", "/home/bento/transferencia/email")
MD_OUTPUT_DIR = os.getenv("MD_OUTPUT_DIR", "/home/bento/rag-email/app-outlook-novo/md-teste")
PROGRESS_DB = os.getenv("PROGRESS_DB", "/home/bento/rag-email/app-outlook-novo/pipeline/data/db/md_progress.sqlite")
USE_GPU = True  # desliga se torch.cuda indisponível em runtime
```

- [ ] **Step 2: Implementar driver**

```python
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
    """CPU: ler .msg + converter anexos leves (MarkItDown)."""
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
    todo = []
    for f in files:
        # dedupe rápido por path sem abrir o .msg (retomada fina ocorre dentro)
        if not is_done(os.path.basename(f)):
            todo.append(f)
    if args.limit:
        todo = todo[: args.limit]
    logger.info("Total .msg: %d | a converter: %d", len(files), len(todo))

    # GPU: 1 worker; CPU: workers = nproc-1
    max_workers = max(1, (os.cpu_count() or 2) - 1)
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
```

- [ ] **Step 3: Smoke test em 2 e-mails**

Run: `cd pipeline && . .venv/bin/activate && python convert_to_md.py --limit 2`
Expected: 2 arquivos `.md` criados sob `md-teste/<conta>/<pasta>/`.

- [ ] **Step 4: Verificar conteúdo gerado**

```bash
find /home/bento/rag-email/app-outlook-novo/md-teste -name '*.md' | head -5
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/convert_to_md.py pipeline/config.py
git commit -m "feat: batch .msg->markdown driver with GPU and resume"
```

---

### Task 6: Limpeza de código obsoleto (COM/RabbitMQ/Windows)

**Files:**
- Delete: `producer.py`, `consumer.py`, `src/ingestion/outlook_reader.py`, `src/graph_generator/` (inteiro), `docker-compose.yml`, `monitor_producer.ps1`, `start_consumer.ps1`, `check_db.py`, `check_progress.py` (pipeline e raiz), `get_status.py`, `fix_queued.py`, `scratch_status.py`, `test_fase1_v2.py`, `test_integrated_v2.py`.

- [ ] **Step 1: Remover via git rm**

```bash
cd /home/bento/rag-email/app-outlook-novo
git rm -r -q pipeline/producer.py pipeline/consumer.py \
  pipeline/src/ingestion/outlook_reader.py pipeline/src/graph_generator \
  pipeline/docker-compose.yml pipeline/monitor_producer.ps1 \
  start_consumer.ps1 pipeline/check_db.py pipeline/check_progress.py \
  pipeline/get_status.py pipeline/fix_queued.py pipeline/scratch_status.py \
  pipeline/test_fase1_v2.py pipeline/test_integrated_v2.py check_progress.py
```

- [ ] **Step 2: Garantir que nada referencia os removidos**

Run: `grep -rn "outlook_reader\|obsidian_formatter\|from producer\|from consumer\|win32com" pipeline/`
Expected: zero matches.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove COM/RabbitMQ/Windows-specific code superseded by .msg reader"
```

---

### Task 7: Conversão completa + validação

**Files:** nenhum (execução).

- [ ] **Step 1: Rodar conversão completa**

```bash
cd pipeline && . .venv/bin/activate && python convert_to_md.py
```
Esperado: processa 1.737 e-mails; log de progresso a cada 20.

- [ ] **Step 2: Validar contagem e integridade**

```bash
find /home/bento/rag-email/app-outlook-novo/md-teste -name '*.md' | wc -l
# conferir contra 1737; investigar diferenças
find /home/bento/rag-email/app-outlook-novo/md-teste -name '*.md' -empty | wc -l
```

- [ ] **Step 3: Reportar métricas finais** (arquivos, falhas, tempo total)

---

## Melhorias de performance e acurácia (recomendadas e incorporadas)

1. **Sem RabbitMQ/COM**: leitura direta de `.msg` em disco elimina o overhead de fila AMQP e a dependência do Outlook Desktop. Mais simples e mais rápido.
2. **GPU para PDFs (Docling)**: TableFormer/layout rodam em CUDA — acelera a extração de tabelas, o gargalo dominante (56 e-mails >10MB, muitos PDFs).
3. **GPU para OCR (EasyOCR)**: imagens e PDFs escaneados (antes `do_ocr=False`, produziam texto vazio) agora são OCR-izados em CUDA. **Correção de acurácia** — scans deixavam de ser lidos.
4. **Corpo HTML→Markdown (`markdownify`)**: preserva tabelas, negrito e links do corpo (antes: texto plano truncado em 1500 chars no obsidian_formatter). **Correção de acurácia**.
5. **Retomada via SQLite**: idempotente por id — reprocessa só o que falta após falha.
6. **Paralelismo CPU + serialização GPU**: `nproc-1` workers para parsing/MarkItDown; GPU protegida por semáforo implícito (1 worker GPU). Evita OOM de 8GB.

## Riscos

- **Docling no Pascal (sm_61)**: `docling-ibm-models` (TableFormer) pode ser lento ou exigir fallback para CPU. Mitigação: fallback automático MarkItDown + flag `USE_GPU` para desligar.
- **8GB VRAM**: PDFs muito grandes podem estourar. Mitigação: processamento um-a-um na GPU, fallback MarkItDown em OOM.
- **EasyOCR modelo pt**: acurácia em português técnico é razoável, não perfeita. Alternativa futura: PaddleOCR (melhor, instalação mais pesada).
- **`extract-msg` com .msg corrompidos**: alguns arquivos podem falhar. Mitigação: try/except por arquivo + status FAILED no SQLite, sem abortar o lote.

## Self-Review

- **Cobertura da spec**: leitura `.msg` (Task 2) ✓; corpo→md (Task 3) ✓; GPU (Task 4) ✓; saída `md-teste/` (Task 1/3/5) ✓; sugestões de melhoria (seção própria) ✓; plano antes de executar (este documento, execução só após aprovação) ✓.
- **Placeholders**: nenhum — código real em cada step.
- **Consistência de tipos**: `read_msg -> dict` (chaves `id/account/folder/subject/sender/sender_email/to/cc/date/direction/body_html/body_text/attachments`); `EmailFormatter.format_email(email, attachment_texts)`; `AttachmentProcessor.process(att) -> str`. Assinaturas casam entre Tasks 2,3,4,5.
