# Flask Integration Guide

> Интеграция SemanticCore в Flask приложения

---

## Обзор

SemanticCore легко интегрируется в Flask через **Application Factory** паттерн. Библиотека предоставляет **ComponentFactory** для создания всех компонентов (embeddings, LLM, vision, transcription) через unified конфигурацию.

**Ключевые преимущества:**
- ✅ Единая конфигурация `semantic.toml` для всех провайдеров
- ✅ Поддержка локальных и облачных моделей
- ✅ Graceful degradation (приложение работает даже если Vision недоступен)
- ✅ DI через `app.extensions` (Flask стандарт)

---

## Quick Start

### 1. Установка

```bash
# Базовая установка
pip install semantic-core

# С локальными моделями (macOS Apple Silicon)
pip install semantic-core[local]

# Для Flask интеграции
pip install flask pydantic-settings
```

### 2. Структура проекта

```
myapp/
├── app/
│   ├── __init__.py          # Application factory
│   ├── extensions.py        # SemanticCore инициализация
│   ├── config.py            # Flask + Semantic config
│   └── routes/
│       ├── search.py        # Search endpoint
│       ├── ingest.py        # Document upload
│       └── chat.py          # RAG chat
├── semantic.toml            # SemanticCore конфигурация
├── .env                     # Секреты (API keys)
└── run.py                   # Точка входа
```

---

## Application Factory Pattern

### `app/__init__.py`

```python
from flask import Flask
from app.extensions import init_semantic_core

def create_app(config_overrides: dict | None = None) -> Flask:
    """Фабрика Flask приложения с SemanticCore интеграцией."""
    app = Flask(__name__)
    
    # Загрузка конфигурации
    from app.config import FlaskAppConfig
    config = FlaskAppConfig()
    app.config.from_mapping(config.to_flask_config())
    
    # Инициализация SemanticCore
    init_semantic_core(app)
    
    # Register blueprints
    from app.routes import search, ingest, chat
    app.register_blueprint(search.bp)
    app.register_blueprint(ingest.bp)
    app.register_blueprint(chat.bp)
    
    return app
```

---

## Extensions Module

### `app/extensions.py`

Этот модуль инициализирует SemanticCore через ComponentFactory.

```python
"""SemanticCore интеграция для Flask."""

from flask import Flask, current_app
from semantic_core import get_config
from semantic_core.core.factory import ComponentFactory
from semantic_core.pipeline import SemanticCore
from semantic_core.utils.logger import get_logger

logger = get_logger("flask.extensions")


def init_semantic_core(app: Flask) -> None:
    """
    Инициализация SemanticCore с Multi-Provider поддержкой.
    
    Компоненты сохраняются в app.extensions:
    - semantic_core: SemanticCore instance
    - semantic_config: SemanticConfig instance
    """
    
    # 1. Загрузить конфигурацию
    config = get_config()
    logger.info(f"📋 Loaded config: embedding_provider={config.defaults.embedding_provider}")
    
    # 2. Создать Embedder (критичный компонент)
    try:
        embedder = ComponentFactory.create_embedder(config)
        logger.info(
            f"✅ Embedder initialized: "
            f"{config.defaults.embedding_provider} ({embedder.dimension}D)"
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize embedder: {e}")
        raise RuntimeError("Embedder is required for SemanticCore") from e
    
    # 3. Создать LLM (опционально)
    try:
        llm = ComponentFactory.create_llm(config)
        logger.info(f"✅ LLM initialized: {config.defaults.llm_provider}")
    except Exception as e:
        logger.warning(f"⚠️ LLM not available: {e}")
        llm = None
    
    # 4. Создать Vision Analyzer (опционально)
    try:
        vision = ComponentFactory.create_vision(config)
        logger.info(f"✅ Vision initialized: {config.defaults.vision_provider}")
    except Exception as e:
        logger.warning(f"⚠️ Vision not available: {e}")
        vision = None
    
    # 5. Создать Transcriber (опционально)
    try:
        transcriber = ComponentFactory.create_transcriber(config)
        logger.info(f"✅ Transcriber initialized: {config.defaults.transcription_provider}")
    except Exception as e:
        logger.warning(f"⚠️ Transcriber not available: {e}")
        transcriber = None
    
    # 6. Собрать SemanticCore
    from semantic_core.integrations.peewee import PeeweeVectorStore
    
    store = PeeweeVectorStore(
        db_path=config.db_path,
        dimension=embedder.dimension
    )
    
    core = SemanticCore(
        embedder=embedder,
        store=store,
        llm=llm,
        vision_analyzer=vision,
        transcriber=transcriber
    )
    
    # 7. Сохранить в Flask extensions
    app.extensions['semantic_core'] = core
    app.extensions['semantic_config'] = config
    
    logger.info("🎉 SemanticCore initialized successfully")


def get_semantic_core() -> SemanticCore:
    """Helper для получения SemanticCore из Flask context."""
    return current_app.extensions['semantic_core']


def get_semantic_config():
    """Helper для получения SemanticConfig из Flask context."""
    return current_app.extensions['semantic_config']
```

**Ключевые особенности:**

1. **Graceful Degradation:**
   - Embedder — критичный (exception если failed)
   - LLM, Vision, Transcriber — опциональные (warning если failed)
   
2. **Логирование:**
   - Показывает выбранный провайдер при старте
   - Эмодзи для читаемости (✅ success, ⚠️ warning, ❌ error)

3. **Flask Extensions Pattern:**
   - Компоненты в `app.extensions` dict
   - Доступ через `current_app.extensions['semantic_core']`

---

## Configuration

### `app/config.py`

```python
"""Flask + SemanticCore конфигурация через Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class FlaskAppConfig(BaseSettings):
    """Конфигурация Flask приложения."""
    
    # Flask settings
    secret_key: str = "dev-secret-key"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 5000
    
    # Upload settings
    upload_folder: Path = Path("uploads")
    max_content_length: int = 16 * 1024 * 1024  # 16MB
    
    model_config = SettingsConfigDict(
        env_prefix="FLASK_",
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    def to_flask_config(self) -> dict:
        """Конвертировать в Flask app.config dict."""
        return {
            "SECRET_KEY": self.secret_key,
            "DEBUG": self.debug,
            "UPLOAD_FOLDER": str(self.upload_folder),
            "MAX_CONTENT_LENGTH": self.max_content_length,
        }
```

### `semantic.toml`

```toml
# SemanticCore Configuration для Flask App

[defaults]
embedding_provider = "gemini"     # "gemini", "local", "openai"
llm_provider = "gemini"
vision_provider = "gemini"
transcription_provider = "none"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
embedding_model = "text-embedding-004"
dimension = 768
llm_model = "gemini-2.0-flash-exp"

[providers.local]
# Локальные модели (macOS Apple Silicon)
embedding_model = "qwen3-embedding"  # 1024D, MRL support
device = "mps"

[storage]
db_path = "instance/semantic.db"

[processing]
chunk_size = 1000
code_chunk_size = 1500
```

### `.env`

```bash
# Flask Settings
FLASK_SECRET_KEY=your-secret-key
FLASK_DEBUG=true

# Gemini API (для Cloud Provider)
GEMINI_API_KEY=your-gemini-api-key

# SemanticCore Overrides (optional)
# SEMANTIC_DEFAULTS__EMBEDDING_PROVIDER=local
# SEMANTIC_DB_PATH=custom/path/semantic.db
```

**Приоритет конфигурации:**
1. Environment variables (`.env`)
2. `semantic.toml`
3. Defaults в коде

---

## Routes Examples

### Search Endpoint

```python
"""app/routes/search.py"""

from flask import Blueprint, request, jsonify
from app.extensions import get_semantic_core

bp = Blueprint("search", __name__, url_prefix="/api/search")


@bp.route("/", methods=["POST"])
def search():
    """Гибридный поиск (vector + FTS5 + RRF)."""
    data = request.get_json()
    query = data.get("query")
    top_k = data.get("top_k", 5)
    
    if not query:
        return jsonify({"error": "Query required"}), 400
    
    # Получить SemanticCore из Flask context
    core = get_semantic_core()
    
    # Выполнить поиск
    results = core.search(
        query=query,
        top_k=top_k,
        mode="hybrid"  # "vector", "sql", "hybrid"
    )
    
    # Сериализация
    return jsonify({
        "query": query,
        "results": [
            {
                "id": r.chunk_id,
                "content": r.content,
                "score": r.score,
                "source": r.source_file
            }
            for r in results
        ]
    })
```

### Ingest Endpoint

```python
"""app/routes/ingest.py"""

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
from app.extensions import get_semantic_core

bp = Blueprint("ingest", __name__, url_prefix="/api/ingest")


@bp.route("/", methods=["POST"])
def ingest_file():
    """Загрузить и проиндексировать файл."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    filename = secure_filename(file.filename)
    
    # Сохранить файл
    upload_folder = Path("uploads")
    upload_folder.mkdir(exist_ok=True)
    file_path = upload_folder / filename
    file.save(file_path)
    
    # Проиндексировать
    core = get_semantic_core()
    
    result = core.ingest(
        sources=[str(file_path)],
        recursive=False
    )
    
    return jsonify({
        "message": f"Ingested {filename}",
        "documents": result.total_documents,
        "chunks": result.total_chunks
    })
```

### Chat Endpoint (RAG)

```python
"""app/routes/chat.py"""

from flask import Blueprint, request, jsonify
from app.extensions import get_semantic_core

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@bp.route("/", methods=["POST"])
def chat():
    """RAG ответ на вопрос с источниками."""
    data = request.get_json()
    question = data.get("question")
    
    if not question:
        return jsonify({"error": "Question required"}), 400
    
    core = get_semantic_core()
    
    # RAG Engine
    from semantic_core.core.rag import RAGEngine
    rag = RAGEngine(semantic_core=core)
    
    result = rag.answer(question)
    
    return jsonify({
        "question": question,
        "answer": result.answer,
        "sources": [
            {
                "content": s.content[:200],
                "source": s.source_file,
                "score": s.score
            }
            for s in result.sources
        ]
    })
```

---

## Switching Providers

### Cloud Mode (Gemini)

```toml
[defaults]
embedding_provider = "gemini"
llm_provider = "gemini"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
dimension = 768
```

```bash
GEMINI_API_KEY=your-key python run.py
```

### Local Mode (macOS)

```toml
[defaults]
embedding_provider = "local"
llm_provider = "gemini"  # LLM остаётся cloud

[providers.local]
embedding_model = "qwen3-embedding"
device = "mps"
```

```bash
python run.py  # API key не нужен для embeddings
```

⚠️ **ВАЖНО:** При смене провайдера нужно пересоздать БД (dimension change):

```bash
rm instance/semantic.db
flask ingest ./docs
```

---

## Production Checklist

### Security

- [ ] Установить `FLASK_SECRET_KEY` (random string)
- [ ] Использовать environment variables для API keys
- [ ] Не коммитить `.env` в git
- [ ] Включить HTTPS в production

### Performance

- [ ] Использовать `gunicorn` вместо Flask dev server
- [ ] Настроить connection pool для БД
- [ ] Включить query cache (Phase 12.1)
- [ ] Настроить rate limiting

### Monitoring

- [ ] Логирование через structured logger
- [ ] Metrics через Prometheus (provider performance)
- [ ] Error tracking (Sentry)
- [ ] Health check endpoint

### Configuration

- [ ] Использовать production API keys
- [ ] Настроить batch processing для Gemini (экономия)
- [ ] Выбрать оптимальную dimension (768 vs 1024)
- [ ] Настроить graceful shutdown

---

## Troubleshooting

### Dimension Mismatch Error

**Симптом:**
```
❌ Dimension mismatch! Embedder=1024D, DB=768D
```

**Решение:**
1. Удалить БД: `rm instance/semantic.db`
2. Обновить `semantic.toml` с правильной dimension
3. Переиндексировать: `flask ingest ./docs`

**См. также:** [Local Embeddings Migration](../core/local-embeddings.md#migration)

### MPS Unavailable (Intel Mac)

**Симптом:**
```
⚠️ MPS unavailable, fallback to CPU
```

**Решение:**
Использовать `device = "cpu"` в `semantic.toml` (медленнее, но работает)

### ImportError: MLX not installed

**Симптом:**
```
❌ ImportError: No module named 'mlx'
```

**Решение:**
```bash
pip install 'semantic-core[local]'
```

### API Key Not Set

**Симптом:**
```
❌ GEMINI_API_KEY not set
```

**Решение:**
1. Создать `.env` файл
2. Добавить `GEMINI_API_KEY=your-key`
3. Или использовать Local provider (не требует key)

---

## См. также

- [Local Embeddings Guide](../core/local-embeddings.md) — настройка локальных моделей
- [Multi-Provider Architecture](../../concepts/11_multi_provider.md) — обзор архитектуры
- [ComponentFactory Reference](../../reference/factory.md) — API документация
- [Flask App Example](https://github.com/VladimirMonin/semantic-core/tree/main/examples/flask_app) — полный пример
