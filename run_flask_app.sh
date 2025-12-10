#!/bin/bash
# ============================================
#  Semantic Knowledge Base - Flask App Runner
#  macOS / Linux Shell Script
# ============================================

echo ""
echo " 🧠 Semantic Knowledge Base"
echo " =========================="
echo ""

# Переходим в папку Flask приложения
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/examples/flask_app"

# Проверяем наличие poetry
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry не найден! Установите: pip install poetry"
    exit 1
fi

# Устанавливаем зависимости (если нужно)
echo "📦 Проверка зависимостей..."
poetry install --quiet

# Запускаем приложение
echo ""
echo "🚀 Запуск Flask приложения..."
echo "   URL: http://127.0.0.1:5000"
echo "   Нажмите Ctrl+C для остановки"
echo ""

poetry run python run.py
