"""
Attachment Processor v5 — Estratégia híbrida MarkItDown + Docling GPU + EasyOCR GPU.
Parte da Fase 1 do Pipeline CARACOL (conversão .msg -> Markdown).

Roteamento:
- MarkItDown: MSG, DOCX, TXT, HTML, CSV, PPTX, XLSX (rápido, CPU, subprocesso isolado)
- Docling: PDF (TableFormer + layout, GPU quando disponível) — modelo CACHEADO no worker
- EasyOCR: imagens PNG/JPG/TIFF/BMP (OCR, GPU) — modelo CACHEADO no worker
- Archive Extractor: ZIP, RAR, 7Z, TAR (recursivo)
- MS Project Reader: MPP, MPX (via MPXJ/Java)
- Skip: DWG, EXE, DLL (binários sem texto)

Nota de performance: os modelos EasyOCR/Docling são carregados UMA VEZ por processo
worker (lazy singleton) e reutilizados entre anexos. Recarregar por anexo custava ~3-5s
de load por arquivo — com 7.8k anexos GPU-bound isso somava ~8 horas. O subprocesso
isolado foi mantido apenas no MarkItDown, cujo risco de segfault em binário corrompido
justifica o isolamento (e cuja contagem é baixa).
"""
import os
import gc
import tempfile
import logging
import multiprocessing

from markitdown import MarkItDown
from .format_router import get_engine, get_engine_name, ConversionEngine

logger = logging.getLogger(__name__)

# ── Caches de modelo por processo (lazy singleton) ─────────────────
_EASYOCR_READER = None
_DOCLING_CONVERTER = None


def _get_easyocr_reader():
    """EasyOCR Reader pt+en, carregado uma vez por processo (GPU se disponível)."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        import torch
        import easyocr
        _EASYOCR_READER = easyocr.Reader(["pt", "en"], gpu=torch.cuda.is_available())
    return _EASYOCR_READER


def _get_docling_converter():
    """Docling DocumentConverter, carregado uma vez por processo (GPU se disponível)."""
    global _DOCLING_CONVERTER
    if _DOCLING_CONVERTER is None:
        import torch
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            AcceleratorDevice,
            AcceleratorOptions,
            PdfPipelineOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        if torch.cuda.is_available():
            pipeline_options.accelerator_options = AcceleratorOptions(
                device=AcceleratorDevice.CUDA
            )
        _DOCLING_CONVERTER = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    return _DOCLING_CONVERTER


def _run_markitdown_process(temp_path: str, result_queue: multiprocessing.Queue):
    """Executado em subprocesso para isolar segfaults do MarkItDown ao ler binários severamente corrompidos."""
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(temp_path)
        result_queue.put(("success", result.text_content or ""))
    except Exception as e:
        result_queue.put(("error", str(e)))


class AttachmentProcessor:
    """
    Fábrica que roteia cada anexo para o engine mais adequado.
    Fallback automático: Docling/OCR falhar → MarkItDown → log de erro.
    """
    _md = MarkItDown()          # Sempre carregado (leve, ~50MB)

    # ── Entry point principal ──────────────────────────────────────
    @classmethod
    def process(cls, attachment: dict) -> str:
        """
        Processa um anexo e retorna o texto extraído.
        Roteia automaticamente para o engine correto baseado na extensão.
        """
        name = attachment.get("name", "anexo_desconhecido.bin")
        file_path = attachment.get("file_path")
        data = attachment.get("data")

        if not file_path and not data:
            return ""

        engine = get_engine(name)
        engine_name = get_engine_name(name)

        if file_path and os.path.exists(file_path):
            temp_path = file_path
        else:
            # Fallback para dados em bytes na memória
            fd, temp_path = tempfile.mkstemp(suffix="_" + name)
            os.close(fd)
            with open(temp_path, "wb") as f:
                f.write(data)

        try:
            if engine == ConversionEngine.DOCLING:
                return cls._process_docling_with_fallback(temp_path, name)
            elif engine == ConversionEngine.OCR:
                return cls._process_ocr(temp_path, name)
            elif engine == ConversionEngine.ARCHIVE:
                return cls._process_archive(temp_path, name)
            elif engine == ConversionEngine.MSPROJECT:
                return cls._process_msproject(temp_path, name)
            elif engine == ConversionEngine.SKIP:
                logger.info(f"Pulando anexo binário: {name}")
                return f"[Anexo {name}: Formato binário não processável]"
            else:
                return cls._process_markitdown(temp_path, name)

        except Exception as e:
            logger.error(f"Erro fatal ao processar anexo {name}: {e}")
            return f"[Erro ao processar anexo {name}: {e}]"
        finally:
            if not file_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    # ── MarkItDown (motor padrão, subprocesso isolado) ─────────────
    @classmethod
    def _process_markitdown(cls, temp_path: str, name: str) -> str:
        """Converte via MarkItDown em subprocesso isolado (segfault em binário corrompido)."""
        try:
            ctx = multiprocessing.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_run_markitdown_process, args=(temp_path, q))
            p.start()

            import queue
            try:
                status, data = q.get(timeout=60)
                p.join(timeout=5)

                if p.exitcode != 0 and status != "success":
                    logger.warning(f"MarkItDown crashou pesadamente (exitcode {p.exitcode}) em {name}!")
                    return f"[Anexo {name}: Erro Nativo Severo no MarkItDown]"

                if status == "success":
                    return data
                else:
                    return f"[Anexo {name}: Erro na extração - {data}]"

            except queue.Empty:
                logger.warning(f"MarkItDown timeout (60s) em {name} — matando processo.")
                p.terminate()
                p.join()
                return f"[Anexo {name}: Extração travou (Timeout/SegFault)]"

        except Exception as e:
            logger.error(f"MarkItDown falha de subprocesso em {name}: {e}")
            return f"[Anexo {name}: Erro fatal na extração]"

    # ── Docling (modelo cacheado, GPU) ─────────────────────────────
    @classmethod
    def _process_docling_with_fallback(cls, temp_path: str, name: str) -> str:
        """Docling com modelo cacheado. Fallback: MarkItDown."""
        # Guarda de tamanho: PDFs muito grandes (databooks escaneados) travam/OOM
        # a GTX 1080 (8GB) no TableFormer. Roteia direto para MarkItDown.
        if temp_path and os.path.exists(temp_path):
            size_mb = os.path.getsize(temp_path) / (1024 * 1024)
            if size_mb > 10.0:
                logger.warning(
                    f"Anexo {name} ({size_mb:.1f}MB) excede 10MB — usando MarkItDown (sem Docling/GPU)."
                )
                return cls._process_markitdown(temp_path, name)

        try:
            converter = _get_docling_converter()
            result = converter.convert(temp_path)
            md_text = result.document.export_to_markdown()
            return md_text
        except Exception as e:
            logger.warning(f"Docling falhou em {name}: {e} — fallback MarkItDown.")
            return cls._process_markitdown(temp_path, name)

    # ── OCR (EasyOCR, modelo cacheado, GPU) ────────────────────────
    @classmethod
    def _process_ocr(cls, temp_path: str, name: str) -> str:
        """OCR de imagem com modelo cacheado. Fallback: MarkItDown."""
        try:
            reader = _get_easyocr_reader()
            results = reader.readtext(temp_path, detail=0, paragraph=True)
            text = "\n".join(results).strip()
            if text:
                return text
            logger.warning(f"OCR vazio para {name}.")
        except Exception as e:
            logger.warning(f"OCR falhou para {name}: {e}")
        return cls._process_markitdown(temp_path, name)

    # ── Archive Extractor ──────────────────────────────────────────
    @classmethod
    def _process_archive(cls, temp_path: str, name: str) -> str:
        """Descompacta e processa recursivamente os arquivos internos."""
        try:
            from .archive_extractor import extract_archive
            return extract_archive(temp_path, name, cls._process_internal_file, depth=0)
        except ImportError as e:
            logger.warning(f"Módulo archive_extractor não disponível: {e}")
            return f"[Anexo {name}: Módulo de extração de arquivos não disponível]"
        except Exception as e:
            logger.error(f"Erro ao extrair arquivo compactado {name}: {e}")
            return f"[Anexo {name}: Erro na extração do arquivo compactado - {e}]"

    # ── MS Project Reader ──────────────────────────────────────────
    @classmethod
    def _process_msproject(cls, temp_path: str, name: str) -> str:
        """Lê cronograma MS Project e retorna tabela Markdown."""
        try:
            from .msproject_reader import process_msproject
            return process_msproject(temp_path, name)
        except ImportError as e:
            logger.warning(f"Módulo msproject_reader não disponível: {e}")
            return f"[Anexo {name}: Módulo de leitura MS Project não disponível]"
        except Exception as e:
            logger.error(f"Erro ao ler MS Project {name}: {e}")
            return f"[Anexo {name}: Erro na leitura do cronograma - {e}]"

    # ── Callback para o Archive Extractor ──────────────────────────
    @classmethod
    def _process_internal_file(cls, internal_path: str, internal_name: str) -> str:
        """
        Callback usado pelo archive_extractor para processar cada arquivo
        encontrado dentro de um arquivo compactado.
        """
        engine = get_engine(internal_name)

        if engine == ConversionEngine.DOCLING:
            return cls._process_docling_with_fallback(internal_path, internal_name)
        elif engine == ConversionEngine.OCR:
            return cls._process_ocr(internal_path, internal_name)
        elif engine == ConversionEngine.ARCHIVE:
            # Recursão: arquivo compactado dentro de arquivo compactado
            try:
                from .archive_extractor import extract_archive
                return extract_archive(internal_path, internal_name,
                                       cls._process_internal_file, depth=1)
            except Exception as e:
                return f"[{internal_name}: Erro na extração recursiva - {e}]"
        elif engine == ConversionEngine.MSPROJECT:
            return cls._process_msproject(internal_path, internal_name)
        elif engine == ConversionEngine.SKIP:
            return f"[{internal_name}: Formato binário ignorado]"
        else:
            return cls._process_markitdown(internal_path, internal_name)
