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

# === ВАЖНО: load_dotenv ПЕРЕД всеми импортами! ===
# Pydantic Settings читает env vars при импорте модулей,
# поэтому .env должен быть загружен ДО импорта semantic_core.

repo_root = Path(__file__).parent.parent.parent
flask_app_root = Path(__file__).parent

# Добавляем пути в PYTHONPATH
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(flask_app_root))

# Загружаем .env ДО импорта app (который импортирует semantic_core)
from dotenv import load_dotenv

env_file = repo_root / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)  # override=True для перезаписи
    print(f"[OK] Загружен .env из {env_file}")
else:
    print(f"[WARN] Файл .env не найден: {env_file}")

# Теперь безопасно импортировать app
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
