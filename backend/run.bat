@echo off
REM Menjalankan dasbor di Windows. Klik dua kali file ini, atau jalankan dari cmd/PowerShell.
cd /d "%~dp0"

if not exist ".venv\" (
    echo Membuat virtual environment Python di .venv\ ^(hanya sekali^)...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip -q
    pip install -r requirements.txt -q
) else (
    call .venv\Scripts\activate.bat
)

if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        echo %%A| findstr /r "^#" >nul || set "%%A=%%B"
    )
)

python -m app.main
pause
