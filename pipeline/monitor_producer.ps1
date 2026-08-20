$python_exe = "c:\bento\prg\app-outlook-novo\pipeline\pst_venv\Scripts\python.exe"
$script_path = "c:\bento\prg\app-outlook-novo\pipeline\producer.py"
$env:PYTHONIOENCODING='utf-8'

while ($true) {
    Write-Host "=== INCIO DA VARREDURA DO PRODUTOR ===" -ForegroundColor Cyan
    & $python_exe $script_path
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host "=== PRODUTOR FINALIZOU COM SUCESSO ===" -ForegroundColor Green
        break
    } else {
        Write-Host "=== ALERTA: PRODUTOR CAIU (EXIT CODE: $exitCode). REINICIANDO EM 5 SEGUNDOS... ===" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}
