"""Teste rápido do format_router e imports."""
import sys
sys.path.insert(0, 'c:/bento/prg/app-outlook-novo/pipeline')

from src.ingestion.format_router import get_engine, ConversionEngine

tests = [
    ('contract.pdf', 'DOCLING'),
    ('report.docx', 'MARKITDOWN'),
    ('files.zip', 'ARCHIVE'),
    ('schedule.mpp', 'MSPROJECT'),
    ('program.exe', 'SKIP'),
    ('email.msg', 'MARKITDOWN'),
    ('scan.png', 'DOCLING'),
    ('backup.rar', 'ARCHIVE'),
    ('data.7z', 'ARCHIVE'),
    ('planilha.xlsx', 'MARKITDOWN'),
    ('archive.tar.gz', 'ARCHIVE'),
    ('data.csv', 'MARKITDOWN'),
    ('unknown.xyz', 'MARKITDOWN'),
    ('photo.jpg', 'DOCLING'),
    ('doc.html', 'MARKITDOWN'),
    ('macro.xlsm', 'MARKITDOWN'),
]

passed = 0
for filename, expected in tests:
    result = get_engine(filename).name
    ok = "✅" if result == expected else "❌"
    if result == expected:
        passed += 1
    print(f"  {ok} {filename:25s} -> {result:12s} (esperado: {expected})")

print(f"\n{passed}/{len(tests)} testes passaram")

# Teste do import do attachment_processor
print("\n--- Teste de Import do AttachmentProcessor ---")
try:
    from src.ingestion.attachment_processor import AttachmentProcessor
    print("✅ AttachmentProcessor importado com sucesso")
except Exception as e:
    print(f"❌ Erro: {e}")

# Teste do import do archive_extractor
print("\n--- Teste de Import do ArchiveExtractor ---")
try:
    from src.ingestion.archive_extractor import extract_archive
    print("✅ archive_extractor importado com sucesso")
except Exception as e:
    print(f"❌ Erro: {e}")

# Teste do import do msproject_reader
print("\n--- Teste de Import do MSProjectReader ---")
try:
    from src.ingestion.msproject_reader import process_msproject
    print("✅ msproject_reader importado com sucesso")
except Exception as e:
    print(f"❌ Erro: {e}")

print("\n=== TESTES CONCLUÍDOS ===")
