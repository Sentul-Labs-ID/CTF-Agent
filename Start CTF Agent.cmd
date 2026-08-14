@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo CTF Agent belum terpasang. File .venv\Scripts\pythonw.exe tidak ditemukan.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "frontend\gui.pyw"
