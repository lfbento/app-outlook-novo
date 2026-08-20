"""
Format Router — Decide qual engine usar para cada tipo de arquivo.
Parte da evolução Fase 1 do Pipeline CARACOL.
"""
import os
from enum import Enum


class ConversionEngine(Enum):
    MARKITDOWN = "markitdown"
    DOCLING = "docling"
    MINERU = "mineru"          # Motor de alta fidelidade para PDFs complexos/grandes (>3MB)
    ARCHIVE = "archive"
    MSPROJECT = "msproject"
    SKIP = "skip"


# ── Mapeamento centralizado de extensões → engine ──────────────────
ROUTING_TABLE = {
    # MarkItDown — rápido, já instalado, excelente para texto
    '.msg': ConversionEngine.MARKITDOWN,
    '.eml': ConversionEngine.MARKITDOWN,
    '.docx': ConversionEngine.MARKITDOWN,
    '.doc': ConversionEngine.MARKITDOWN,
    '.txt': ConversionEngine.MARKITDOWN,
    '.html': ConversionEngine.MARKITDOWN,
    '.htm': ConversionEngine.MARKITDOWN,
    '.csv': ConversionEngine.MARKITDOWN,
    '.json': ConversionEngine.MARKITDOWN,
    '.xml': ConversionEngine.MARKITDOWN,
    '.rtf': ConversionEngine.MARKITDOWN,
    '.md': ConversionEngine.MARKITDOWN,
    '.pptx': ConversionEngine.MARKITDOWN,
    '.ppt': ConversionEngine.MARKITDOWN,
    '.xlsx': ConversionEngine.MARKITDOWN,
    '.xls': ConversionEngine.MARKITDOWN,
    '.xlsm': ConversionEngine.MARKITDOWN,
    '.xlsb': ConversionEngine.MARKITDOWN,

    # Docling — alta fidelidade para PDFs e imagens (TableFormer + OCR)
    '.pdf': ConversionEngine.DOCLING,
    '.png': ConversionEngine.DOCLING,
    '.jpg': ConversionEngine.DOCLING,
    '.jpeg': ConversionEngine.DOCLING,
    '.tiff': ConversionEngine.DOCLING,
    '.tif': ConversionEngine.DOCLING,
    '.bmp': ConversionEngine.DOCLING,

    # Arquivos compactados
    '.zip': ConversionEngine.ARCHIVE,
    '.rar': ConversionEngine.ARCHIVE,
    '.7z': ConversionEngine.ARCHIVE,
    '.tar': ConversionEngine.ARCHIVE,
    '.gz': ConversionEngine.ARCHIVE,
    '.tgz': ConversionEngine.ARCHIVE,
    '.bz2': ConversionEngine.ARCHIVE,
    '.xz': ConversionEngine.ARCHIVE,

    # MS Project
    '.mpp': ConversionEngine.MSPROJECT,
    '.mpx': ConversionEngine.MSPROJECT,
    '.mspdi': ConversionEngine.MSPROJECT,

    # Ignorados (binários sem texto)
    '.dwg': ConversionEngine.SKIP,
    '.dxf': ConversionEngine.SKIP,
    '.exe': ConversionEngine.SKIP,
    '.bin': ConversionEngine.SKIP,
    '.dll': ConversionEngine.SKIP,
    '.iso': ConversionEngine.SKIP,
    '.msi': ConversionEngine.SKIP,
    '.dat': ConversionEngine.SKIP,
    '.bak': ConversionEngine.SKIP,
}


def get_engine(filename: str) -> ConversionEngine:
    """
    Retorna o engine adequado para o arquivo baseado na extensão.
    Trata casos especiais como .tar.gz, .tar.bz2, .tar.xz.
    Default: MARKITDOWN (tenta processar como texto genérico).
    """
    lower = filename.lower()

    # Tratamento especial para extensões compostas
    if lower.endswith(('.tar.gz', '.tar.bz2', '.tar.xz')):
        return ConversionEngine.ARCHIVE

    ext = os.path.splitext(lower)[1]
    return ROUTING_TABLE.get(ext, ConversionEngine.MARKITDOWN)


def get_engine_name(filename: str) -> str:
    """Retorna o nome legível do engine para logging e formatação."""
    engine = get_engine(filename)
    return engine.value.capitalize()
