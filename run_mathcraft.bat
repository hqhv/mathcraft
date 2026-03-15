@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
    echo Create it first with: py -m venv .venv
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found in project folder.
    pause
    exit /b 1
)

echo Starting MathCraft...
".venv\Scripts\python.exe" -m streamlit run MathCraft.py

endlocal
