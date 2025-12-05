@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Активируем venv и запускаем через python напрямую (надёжнее чем .exe)
call .venv\Scripts\activate.bat
python -c "from semantic_core.cli import main; main()" chat
pause
