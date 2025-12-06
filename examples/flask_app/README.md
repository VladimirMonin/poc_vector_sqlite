# 🧠 Semantic Knowledge Base

> Flask web app для управления базой знаний на базе `semantic_core`.

## 🚀 Быстрый старт

```bash
# Из корня репозитория
cd examples/flask_app

# Установка зависимостей (Flask app использует semantic_core из родительского проекта)
poetry install

# Запуск (development)
flask run --debug

# Или с загрузкой .env
python run.py
```

## 📂 Структура

```
flask_app/
├── app/
│   ├── __init__.py      # create_app() фабрика
│   ├── extensions.py    # SemanticCore интеграция
│   ├── routes/          # Blueprints
│   │   ├── main.py      # Главная страница
│   │   ├── search.py    # Поиск (Phase 12.2)
│   │   ├── ingest.py    # Загрузка (Phase 12.3)
│   │   └── chat.py      # RAG чат (Phase 12.4)
│   ├── templates/       # Jinja2 шаблоны
│   │   ├── base.html    # Bootstrap 5 + HTMX
│   │   └── ...
│   └── static/          # CSS, JS, uploads
├── tests/               # pytest-flask тесты
├── run.py               # Entry point
└── pyproject.toml
```

## ⚙️ Конфигурация

Приложение использует **Pydantic Settings** для конфигурации (как и `semantic_core`).

### Flask App настройки

```bash
# Environment variables (FLASK_ префикс)
export FLASK_SECRET_KEY=your-secret-key
export FLASK_DEBUG=true
export FLASK_HOST=127.0.0.1
export FLASK_PORT=5000
export FLASK_UPLOAD_FOLDER=uploads
export FLASK_MAX_CONTENT_LENGTH=52428800  # 50MB
```

### SemanticCore настройки

```bash
# Gemini API (без префикса)
export GEMINI_API_KEY=your_key

# Или с SEMANTIC_ префиксом
export SEMANTIC_DB_PATH=semantic.db
export SEMANTIC_LOG_LEVEL=INFO
```

Или через `semantic.toml` в корне репозитория.

## 🎨 Стек

- **Flask 3.0** — Web framework
- **Bootstrap 5.3** — UI + Dark Mode
- **HTMX** — Интерактивность без JavaScript
- **semantic_core** — Поиск, RAG, медиа
