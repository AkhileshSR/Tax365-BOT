# Purpose: Activate the local virtual environment and launch Tax365.
# Sample input: PowerShell from the T365_Solution directory.
# Output: Running Telegram bot.
# Dependencies: Python virtual environment and configured .env.

$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run: python -m venv .venv"
    exit 1
}
& ".\.venv\Scripts\python.exe" "main.py"
