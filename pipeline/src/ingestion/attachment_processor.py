"""
Attachment Processor v4 — Estratégia híbrida MarkItDown + Docling GPU + EasyOCR GPU.
Parte da Fase 1 do Pipeline CARACOL (conversão .msg -> Markdown).

Roteamento:
- MarkItDown: MSG, DOCX, TXT, HTML, CSV, PPTX, XLSX (rápido, CPU)
- Docling: PDF (alta fidelidade: TableFormer + layout, GPU quando disponível)
- EasyOCR: imagens PNG/JPG/TIFF/BMP (OCR, GPU quando disponível)
- Archive Extractor: ZIP, RAR, 7Z, TAR (recursivo)
- MS Project Reader: MPP, MPX (via MPXJ/Java)
- Skip: DWG, EXE, DLL (binários sem texto)
"""
import os
import gc
import tempfile
import logging
import signal
import multiprocessing
import subprocess
import traceback

from markitdown import MarkItDown
from .format_router import get_engine, get_engine_name, ConversionEngine

logger = logging.getLogger(__name__)

def _run_docling_process(temp_path: str, result_queue: multiprocessing.Queue):
    """Executado em um subprocesso para isolar possíveis crashes (std::bad_alloc) do C/C++ da biblioteca docling."""
    import gc
    try:
        import torch
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        if torch.cuda.is_available():
            # Acelera layout/TableFormer na GPU (GTX 1080)
            converter.pipeline_options.device = torch.device("cuda")

        result = converter.convert(temp_path)
        md_text = result.document.export_to_markdown()
        result_queue.put(("success", md_text))
    except Exception as e:
        result_queue.put(("error", str(e)))
    finally:
        gc.collect()

def _run_markitdown_process(temp_path: str, result_queue: multiprocessing.Queue):
    """Executado em subprocesso para isolar segfaults do MarkItDown ao ler binários severamente corrompidos."""
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(temp_path)
        result_queue.put(("success", result.text_content or ""))
    except Exception as e:
        result_queue.put(("error", str(e)))


def _run_easyocr_process(temp_path: str, result_queue: multiprocessing.Queue):
    """OCR de imagem em subprocesso (EasyOCR GPU)."""
    try:
        import torch
        import easyocr
        reader = easyocr.Reader(["pt", "en"], gpu=torch.cuda.is_available())
        results = reader.readtext(temp_path, detail=0, paragraph=True)
        result_queue.put(("success", "\n".join(results)))
    except Exception as e:
        result_queue.put(("error", str(e)))



class AttachmentProcessor:
    """
    Fábrica que roteia cada anexo para o engine mais adequado.
    Fallback automático: Docling falhar → MarkItDown → log de erro.
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
            logger.info(f"Convertendo anexo: {name} [Motor: {engine_name}]")

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
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    # ── MarkItDown (motor padrão) ──────────────────────────────────
    @classmethod
    def _process_markitdown(cls, temp_path: str, name: str) -> str:
        """Converte usando MarkItDown blindado em subprocesso — rápido, mas pode ter segfault nativo em arquivos corrompidos."""
        logger.info(f"Processando {name} com MarkItDown em subprocesso isolado...")
        try:
            ctx = multiprocessing.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_run_markitdown_process, args=(temp_path, q))
            p.start()
            
            import queue
            try:
                # O MarkItDown roda em segundos. O limite de 60s previne hangs infinitos em docx complexos
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
                logger.warning(f"MarkItDown timeout excedido (60s) ou SegFault silencioso em {name} — matando processo.")
                p.terminate()
                p.join()
                return f"[Anexo {name}: Extração travou (Timeout/SegFault)]"
                
        except Exception as e:
            logger.error(f"MarkItDown falha de subprocesso em {name}: {e}")
            return f"[Anexo {name}: Erro fatal na extração]"

    # ── Docling com fallback (via multiprocessing) ─────────────────
    @classmethod
    def _process_docling_with_fallback(cls, temp_path: str, name: str) -> str:
        """
        Executa Docling em processo isolado (GPU quando disponível) para mitigar
        crashes pesados (std::bad_alloc). Fallback: MarkItDown.
        """

        logger.info(f"Iniciando Docling em processo isolado para {name}...")
        
        try:
            ctx = multiprocessing.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_run_docling_process, args=(temp_path, q))
            p.start()
            
            import queue
            try:
                # O PULO DO GATO: Sempre leia da fila *antes* de fazer o join!
                # Se o texto MarkDown for enorme, dar `.join()` antes de `.get()`
                # enche o buffer OSI Pipe e mata os dois processos de deadlock!
                status, data = q.get(timeout=120)
                
                # Agora sim, processo deve terminar suavemente em <10s
                p.join(timeout=10)
                
                if p.exitcode != 0 and status != "success":
                    logger.warning(f"Docling processo interrompido (exitcode {p.exitcode}) em {name}. Tentando recuperação...")
                    return cls._route_pdf_fallback(temp_path, name)
                    
                if status == "success":
                    logger.info(f"Docling processou {name} com sucesso ✅")
                    return data
                else:
                    logger.warning(f"Docling falhou internamente em {name}: {data} — tentando recuperação...")
                    return cls._route_pdf_fallback(temp_path, name)
                    
            except queue.Empty:
                logger.warning(f"Docling timeout excedido (120s) em {name} — matando processo e tentando recuperação...")
                p.terminate()
                p.join()
                return cls._route_pdf_fallback(temp_path, name)
            except Exception as e:
                logger.warning(f"Falha inter-processos com Docling para {name}: {e} — tentando recuperação...")
                return cls._route_pdf_fallback(temp_path, name)

        except BaseException as root_e:
            logger.error(f"Erro ao instanciar subprocesso do docling p/ {name}: {root_e}")

        # Fallback se tudo der errado
        return cls._route_pdf_fallback(temp_path, name)

    @classmethod
    def _route_pdf_fallback(cls, temp_path: str, name: str) -> str:
        """Fallback universal: MarkItDown."""
        return cls._process_markitdown(temp_path, name)


    # ── OCR (imagens, EasyOCR GPU) ─────────────────────────────────
    @classmethod
    def _process_ocr(cls, temp_path: str, name: str) -> str:
        """OCR de imagem em subprocesso isolado. Fallback: MarkItDown."""
        logger.info(f"OCR (GPU) de {name} ...")
        try:
            ctx = multiprocessing.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_run_easyocr_process, args=(temp_path, q))
            p.start()
            import queue
            try:
                status, data = q.get(timeout=300)
                p.join(timeout=10)
                if status == "success" and data.strip():
                    return data
            except queue.Empty:
                logger.warning(f"OCR timeout em {name} — matando processo.")
                p.terminate()
                p.join()
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
