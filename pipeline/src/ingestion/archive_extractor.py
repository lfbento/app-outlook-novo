"""
Archive Extractor — Descompacta ZIP, RAR, 7Z, TAR e processa recursivamente.
Parte da evolução Fase 1 do Pipeline CARACOL.

Segurança:
- MAX_EXTRACT_SIZE: 50MB total
- MAX_RECURSION_DEPTH: 2 níveis
- MAX_FILES_PER_ARCHIVE: 100 arquivos
- MAX_SINGLE_FILE_SIZE: 10MB por arquivo
"""
import os
import zipfile
import tarfile
import tempfile
import shutil
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Configurar caminho do UnRAR (WinRAR instalado via winget)
_UNRAR_PATHS = [
    r"C:\Program Files\WinRAR\UnRAR.exe",
    r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
]
for _path in _UNRAR_PATHS:
    if os.path.exists(_path):
        try:
            import rarfile
            rarfile.UNRAR_TOOL = _path
        except ImportError:
            pass
        break

# ── Limites de Segurança ───────────────────────────────────────────
MAX_EXTRACT_SIZE = 50 * 1024 * 1024       # 50MB total extraído
MAX_SINGLE_FILE_SIZE = 10 * 1024 * 1024   # 10MB por arquivo individual
MAX_FILES_PER_ARCHIVE = 100                # máx. arquivos por archive
MAX_RECURSION_DEPTH = 2                    # zip dentro de zip, máx. 2 níveis

# Extensões que devemos ignorar dentro do archive
SKIP_INTERNAL = {'.exe', '.dll', '.bin', '.iso', '.msi', '.bak', '.dat',
                 '.dwg', '.dxf', '.psd', '.ai', '.indd'}


def extract_archive(temp_path: str, filename: str,
                    process_file_fn: Callable[[str, str], str],
                    depth: int = 0) -> str:
    """
    Extrai um arquivo compactado e processa recursivamente seu conteúdo.

    Args:
        temp_path: caminho do arquivo compactado no disco
        filename: nome original do arquivo (para detecção de formato)
        process_file_fn: função callback(temp_path, filename) -> str
                         que processa cada arquivo interno
        depth: nível atual de recursão

    Returns:
        Texto consolidado dos arquivos internos
    """
    if depth > MAX_RECURSION_DEPTH:
        return f"[📦 {filename}: Profundidade máxima de descompactação atingida ({MAX_RECURSION_DEPTH} níveis)]"

    lower = filename.lower()
    extract_dir = tempfile.mkdtemp(prefix="caracol_archive_")

    try:
        # ── Detectar formato e extrair ─────────────────────────────
        if lower.endswith('.zip'):
            extracted_files = _extract_zip(temp_path, extract_dir)
        elif lower.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz', '.gz')):
            extracted_files = _extract_tar(temp_path, extract_dir, lower)
        elif lower.endswith('.7z'):
            extracted_files = _extract_7z(temp_path, extract_dir)
        elif lower.endswith('.rar'):
            extracted_files = _extract_rar(temp_path, extract_dir)
        else:
            return f"[📦 {filename}: Formato de compactação não reconhecido]"

        if not extracted_files:
            return f"[📦 {filename}: Arquivo compactado vazio]"

        # ── Processar cada arquivo extraído ────────────────────────
        results = []
        total_size = 0
        files_processed = 0

        results.append(f"[📦 Conteúdo do arquivo compactado: {filename} ({len(extracted_files)} arquivo(s))]")

        for internal_path, internal_name in extracted_files:
            # Limite de arquivos
            if files_processed >= MAX_FILES_PER_ARCHIVE:
                results.append(f"\n[⚠️ Limite de {MAX_FILES_PER_ARCHIVE} arquivos atingido, restantes ignorados]")
                break

            # Limite de tamanho individual
            try:
                file_size = os.path.getsize(internal_path)
            except OSError:
                continue

            if file_size > MAX_SINGLE_FILE_SIZE:
                results.append(f"\n── {internal_name} ── [Ignorado: {file_size // (1024*1024)}MB excede limite de {MAX_SINGLE_FILE_SIZE // (1024*1024)}MB]")
                continue

            # Limite de tamanho total
            total_size += file_size
            if total_size > MAX_EXTRACT_SIZE:
                results.append(f"\n[⚠️ Limite de {MAX_EXTRACT_SIZE // (1024*1024)}MB total atingido]")
                break

            # Verificar extensão interna
            ext = os.path.splitext(internal_name)[1].lower()
            if ext in SKIP_INTERNAL:
                results.append(f"\n── {internal_name} ── [Formato binário ignorado]")
                files_processed += 1
                continue

            # Processar via callback (que usa o router)
            try:
                text = process_file_fn(internal_path, internal_name)
                if text and text.strip():
                    results.append(f"\n── {internal_name} ──")
                    results.append(text)
                else:
                    results.append(f"\n── {internal_name} ── [Sem texto extraído]")
            except Exception as e:
                results.append(f"\n── {internal_name} ── [Erro: {e}]")

            files_processed += 1

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Erro ao extrair {filename}: {e}")
        return f"[📦 {filename}: Erro na extração - {e}]"

    finally:
        # Limpa diretório temporário
        try:
            shutil.rmtree(extract_dir, ignore_errors=True)
        except Exception:
            pass


# ── Extratores por formato ─────────────────────────────────────────

def _extract_zip(path: str, dest: str) -> list:
    """Extrai ZIP e retorna lista de (caminho_extraído, nome_original)."""
    files = []
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Proteção contra path traversal
                member_name = os.path.basename(info.filename)
                if not member_name:
                    continue
                target = os.path.join(dest, member_name)
                try:
                    with zf.open(info) as src, open(target, 'wb') as dst:
                        dst.write(src.read())
                    files.append((target, member_name))
                except Exception as e:
                    logger.debug(f"Erro extraindo {info.filename} do ZIP: {e}")
    except zipfile.BadZipFile:
        logger.warning(f"Arquivo ZIP corrompido: {path}")
    return files


def _extract_tar(path: str, dest: str, lower: str) -> list:
    """Extrai TAR/TAR.GZ/TAR.BZ2/TAR.XZ."""
    files = []

    # Determinar modo de abertura
    if lower.endswith(('.tar.gz', '.tgz')):
        mode = 'r:gz'
    elif lower.endswith('.tar.bz2'):
        mode = 'r:bz2'
    elif lower.endswith('.tar.xz'):
        mode = 'r:xz'
    elif lower.endswith('.gz') and not lower.endswith('.tar.gz'):
        # .gz puro (não tar) — descomprime como gzip simples
        import gzip
        out_name = os.path.basename(path).replace('.gz', '') or 'arquivo_descompactado'
        target = os.path.join(dest, out_name)
        try:
            with gzip.open(path, 'rb') as gz, open(target, 'wb') as out:
                out.write(gz.read())
            files.append((target, out_name))
        except Exception as e:
            logger.warning(f"Erro descompactando GZ: {e}")
        return files
    else:
        mode = 'r'

    try:
        with tarfile.open(path, mode) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                member_name = os.path.basename(member.name)
                if not member_name:
                    continue
                target = os.path.join(dest, member_name)
                try:
                    f = tf.extractfile(member)
                    if f:
                        with open(target, 'wb') as out:
                            out.write(f.read())
                        files.append((target, member_name))
                except Exception as e:
                    logger.debug(f"Erro extraindo {member.name} do TAR: {e}")
    except Exception as e:
        logger.warning(f"Erro abrindo TAR: {e}")
    return files


def _extract_7z(path: str, dest: str) -> list:
    """Extrai 7Z usando py7zr."""
    files = []
    try:
        import py7zr
        with py7zr.SevenZipFile(path, mode='r') as z:
            z.extractall(path=dest)
        # Listar arquivos extraídos
        for root, dirs, filenames in os.walk(dest):
            for fname in filenames:
                full = os.path.join(root, fname)
                files.append((full, fname))
    except ImportError:
        logger.warning("py7zr não instalado — arquivos .7z não podem ser extraídos")
    except Exception as e:
        logger.warning(f"Erro extraindo 7Z: {e}")
    return files


def _extract_rar(path: str, dest: str) -> list:
    """Extrai RAR usando rarfile (requer unrar no PATH)."""
    files = []
    try:
        import rarfile
        with rarfile.RarFile(path) as rf:
            for info in rf.infolist():
                if info.is_dir():
                    continue
                member_name = os.path.basename(info.filename)
                if not member_name:
                    continue
                target = os.path.join(dest, member_name)
                try:
                    with rf.open(info) as src, open(target, 'wb') as dst:
                        dst.write(src.read())
                    files.append((target, member_name))
                except Exception as e:
                    logger.debug(f"Erro extraindo {info.filename} do RAR: {e}")
    except ImportError:
        logger.warning("rarfile não instalado — arquivos .rar não podem ser extraídos")
    except Exception as e:
        if "unrar" in str(e).lower() or "tool" in str(e).lower():
            logger.warning(f"unrar não encontrado no PATH — instale UnRAR de https://www.rarlab.com/rar_add.htm")
        else:
            logger.warning(f"Erro extraindo RAR: {e}")
    return files
