# Добавить Skillik в автозагрузку текущего пользователя (без админа).
$Root = "C:\Users\1\skillik"
$Startup = [Environment]::GetFolderPath("Startup")
$Target = Join-Path $Startup "Skillik.bat"
$Bat = @"
@echo off
cd /d "$Root"
start "" "$Root\.venv\Scripts\pythonw.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*
"@
Set-Content -Path $Target -Value $Bat -Encoding ASCII
Write-Host "Автозагрузка: $Target"
Write-Host "Skillik будет стартовать при входе в Windows."
