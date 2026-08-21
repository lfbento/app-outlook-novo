"""
Configuração central do Pipeline de conversão .msg -> Markdown (GPU).
Todos os caminhos são relativos à raiz do projeto.
"""
import os

# Raiz do projeto = pasta pipeline/
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))

# Raiz do projeto (um nível acima da pasta pipeline/)
PROJECT_DIR = os.path.dirname(PIPELINE_DIR)

# Entrada: pasta com os arquivos .msg exportados do Outlook
EMAIL_SOURCE_DIR = os.getenv("EMAIL_SOURCE_DIR", "/home/bento/transferencia/email")

# Saída: markdown gerado
MD_OUTPUT_DIR = os.getenv("MD_OUTPUT_DIR", os.path.join(PROJECT_DIR, "md-teste"))

# Retomada: SQLite de progresso
PROGRESS_DB = os.getenv("PROGRESS_DB", os.path.join(PIPELINE_DIR, "data", "db", "md_progress.sqlite"))

# GPU (GTX 1080). Desligado em runtime se torch.cuda indisponível.
USE_GPU = True

# Limites de segurança para arquivos compactados
ARCHIVE_MAX_SIZE = 50 * 1024 * 1024      # 50MB total extraído
ARCHIVE_MAX_DEPTH = 2                     # níveis de recursão
ARCHIVE_MAX_FILES = 100                   # arquivos por archive
