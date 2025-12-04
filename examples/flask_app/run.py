#!/usr/bin/env python3
"""Entry point для Flask приложения.

Загружает конфигурацию через Pydantic Settings и запускает сервер.

Usage:
    python run.py
    # или
    flask run --debug
"""

import sys
from pathlib import Path

# Добавляем корень репозитория в PYTHONPATH для импорта semantic_core
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

from app import create_app
from app.config import get_flask_config

# Загружаем конфигурацию (из env + .env)
config = get_flask_config()

app = create_app(config)

if __name__ == "__main__":
    app.run(
        host=config.host,
        port=config.port,
        debug=config.debug,
    )
