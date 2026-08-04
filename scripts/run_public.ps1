# Запуск Skillik для доступа из интернета (белый IP / домен)
# Запускать из папки skillik или через полный путь.

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -ErrorAction SilentlyContinue
if (-not $Root) { $Root = "C:\Users\1\skillik" }
if (-not (Test-Path "$Root\app\main.py")) { $Root = Split-Path $PSScriptRoot -Parent }

Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Не найден venv: $Python. Сначала: python -m venv .venv ; .\.venv\Scripts\pip install -r requirements.txt"
}

# Файрвол (если есть права)
$ruleName = "Skillik HTTP 8000"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any | Out-Null
    } catch {
        Write-Warning "Не удалось создать правило файрвола (запустите PowerShell от администратора): $_"
    }
}

Write-Host "Skillik: http://0.0.0.0:8000 (локально http://127.0.0.1:8000)"
Write-Host "Рабочая папка: $Root"
& $Python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
