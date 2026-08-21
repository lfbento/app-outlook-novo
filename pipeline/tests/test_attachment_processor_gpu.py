from src.ingestion.format_router import get_engine, ConversionEngine


def test_image_routes_to_ocr():
    assert get_engine("scan.png") == ConversionEngine.OCR
    assert get_engine("foto.jpg") == ConversionEngine.OCR
    assert get_engine("doc.pdf") == ConversionEngine.DOCLING
    assert get_engine("plan.xlsx") == ConversionEngine.MARKITDOWN
    assert get_engine("backup.zip") == ConversionEngine.ARCHIVE
    assert get_engine("program.exe") == ConversionEngine.SKIP
