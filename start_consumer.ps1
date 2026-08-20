$env:PYTHONIOENCODING='utf-8'

Write-Host "Iniciando Consumer de Email (Fase 1) - Modo Robusto..." -ForegroundColor Cyan
& "c:\bento\prg\app-outlook-novo\pipeline\pst_venv\Scripts\python.exe" "c:\bento\prg\app-outlook-novo\pipeline\consumer.py"
