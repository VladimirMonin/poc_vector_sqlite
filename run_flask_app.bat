@echo off
chcp 65001 >nul
REM ============================================
REM  Semantic Knowledge Base - Flask App Runner
REM  Windows Batch Script
REM ============================================

echo.
echo  Semantic Knowledge Base
echo  ==========================
echo.

REM Добавляем путь к poetry в PATH
set "PATH=%USERPROFILE%\AppData\Roaming\Python\Scripts;%PATH%"

REM Переходим в папку Flask приложения
cd /d "%~dp0examples\flask_app"

REM Проверяем наличие poetry
where poetry >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Poetry не найден! Установите: pip install poetry
    pause
    exit /b 1
)

REM Устанавливаем зависимости (если нужно)
echo [*] Проверка зависимостей...
call poetry install --quiet

REM Запускаем приложение
echo.
echo [OK] Запуск Flask приложения...
echo     URL: http://127.0.0.1:5000
echo     Нажмите Ctrl+C для остановки
echo.

call poetry run python run.py

pause
