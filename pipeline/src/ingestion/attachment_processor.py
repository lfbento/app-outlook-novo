"""
Attachment Processor v3 — Estratégia híbrida MarkItDown + Docling + MinerU.
Parte da evolução Fase 1 do Pipeline CARACOL.

Roteamento:
- MarkItDown: MSG, DOCX, TXT, HTML, CSV, PPTX, XLSX (rápido)
- Docling: PDF ≤3MB, Imagens (alta fidelidade: TableFormer AI + OCR)
- MinerU: PDF >3MB (sliding-window, CPU-only, venv isolado)
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
    """Executado em um subprocesso para isolar possíveis crashes (std::bad_alloc) do C/C++ da biblioteca docling"""
    import gc
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption
        
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.generate_page_images = False
        
        docling = DocumentConverter(
            format_options={
                "pdf": PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        result = docling.convert(temp_path)
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

# ── Caminho do executável MinerU (venv isolado) ────────────────────
_PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
MINERU_EXE = os.path.join(
    os.path.dirname(_PIPELINE_DIR),  # sobe de src/ingestion → src
    os.pardir,                        # sobe de src → pipeline
    "mineru_venv", "Scripts", "mineru.exe"
)
MINERU_EXE = os.path.normpath(MINERU_EXE)

def _run_mineru_process(temp_path: str, result_queue: multiprocessing.Queue):
    """
    Chama MinerU via subprocess (venv dedicado) para isolar dependências.
    Backend: pipeline (CPU-only, 86.2 OmniDocBench v1.5, sliding-window).
    """
    import shutil
    out_dir = None
    try:
        out_dir = tempfile.mkdtemp(prefix="mineru_")
        result = subprocess.run(
            [MINERU_EXE, "-p", temp_path, "-o", out_dir, "-b", "pipeline"],
            capture_output=True, text=True, timeout=580, encoding="utf-8", errors="replace"
        )
        # MinerU gera subpastas com o nome do arquivo → procurar .md recursivamente
        md_files = []
        for root, dirs, files in os.walk(out_dir):
            for f in files:
                if f.endswith(".md"):
                    md_files.append(os.path.join(root, f))
        
        if md_files:
            # Concatenar todos os .md gerados (documentos multi-página geram múltiplos)
            all_text = []
            for md_file in sorted(md_files):
                with open(md_file, "r", encoding="utf-8", errors="replace") as fh:
                    all_text.append(fh.read())
            result_queue.put(("success", "\n\n".join(all_text)))
        else:
            stderr_snippet = (result.stderr or "")[:500]
            result_queue.put(("error", f"MinerU não gerou .md. stderr: {stderr_snippet}"))
    except subprocess.TimeoutExpired:
        result_queue.put(("error", "MinerU timeout (580s)"))
    except Exception as e:
        result_queue.put(("error", str(e)))
    finally:
        if out_dir and os.path.exists(out_dir):
            try:
                shutil.rmtree(out_dir, ignore_errors=True)
            except Exception:
                pass

from markitdown import MarkItDown
from .format_router import get_engine, get_engine_name, ConversionEngine

logger = logging.getLogger(__name__)

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
        Executa Docling em processo isolado para mitigar "std::bad_alloc" e outros crashes pesados.
        Se falhar ou se o arquivo for > 3.0MB, cai direto para MarkItDown.
        """
        if temp_path and os.path.exists(temp_path):
            file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
            if file_size_mb > 3.0:
                logger.warning(f"Anexo {name} ({file_size_mb:.1f}MB) excede limite seguro p/ Docling (3MB). Roteando para MinerU (sliding-window)...")
                return cls._process_mineru_with_fallback(temp_path, name)

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
        """Roteia para MinerU se for PDF, senão usa MarkItDown."""
        if name.lower().endswith('.pdf'):
            logger.info(f"Recuperação: Roteando PDF {name} para o MinerU...")
            return cls._process_mineru_with_fallback(temp_path, name)
        return cls._process_markitdown(temp_path, name)


    # ── MinerU (motor de alta fidelidade para PDFs grandes) ────────
    @classmethod
    def _process_mineru_with_fallback(cls, temp_path: str, name: str) -> str:
        """
        Executa MinerU em subprocesso isolado (venv dedicado: mineru_venv).
        Backend: pipeline (CPU-only, 86.2 OmniDocBench v1.5).
        Fallback: MarkItDown se falhar ou timeout (10 min).
        """
        import queue as queue_module

        if not os.path.exists(MINERU_EXE):
            logger.warning(f"MinerU não instalado ({MINERU_EXE}). Usando MarkItDown como fallback para {name}.")
            return cls._process_markitdown(temp_path, name)

        logger.info(f"Iniciando MinerU para {name} (arquivo complexo/grande)...")
        try:
            ctx = multiprocessing.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_run_mineru_process, args=(temp_path, q))
            p.start()
            try:
                status, data = q.get(timeout=600)  # 10 min max
                p.join(timeout=10)

                if status == "success":
                    logger.info(f"MinerU processou {name} com sucesso ✅ ({len(data)} chars)")
                    return data
                else:
                    logger.warning(f"MinerU falhou em {name}: {data} — usando MarkItDown...")
            except queue_module.Empty:
                logger.warning(f"MinerU timeout (10min) em {name} — matando processo e usando MarkItDown.")
                p.terminate()
                p.join()
        except Exception as e:
            logger.error(f"Erro ao iniciar MinerU para {name}: {e}")

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
