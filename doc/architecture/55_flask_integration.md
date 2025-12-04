# 🌐 Episode 55: Flask Integration

> Как интегрировать SemanticCore в веб-приложение Flask

---

## 🎯 Зачем Web App?

CLI удобен для разработчика, но для **пользователей** нужен веб-интерфейс:

- Поиск через браузер без знания командной строки
- Загрузка документов через drag-and-drop
- Интерактивный RAG-чат с историей
- Визуализация статистики базы знаний

**Flask + SemanticCore = Semantic Knowledge Base:**

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser                          │
│  📱 Dashboard  🔍 Search  📁 Upload  💬 Chat            │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    Flask App                            │
│                                                         │
│   routes/main.py    → Dashboard, Health                │
│   routes/search.py  → Semantic/Hybrid search           │
│   routes/ingest.py  → Document upload                  │
│   routes/chat.py    → RAG conversations                │
└───────────────────────┬─────────────────────────────────┘
                        │ Python API
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   SemanticCore                          │
│                                                         │
│   Embedder → Store → Splitter → RAGEngine              │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗 Application Factory

Flask рекомендует **Factory Pattern** для создания приложений:

```python
def create_app(config: dict | None = None) -> Flask:
    """Создать Flask приложение."""
    app = Flask(__name__)
    
    # 1. Загрузка конфигурации
    flask_config = get_flask_config()
    app.config.from_mapping(flask_config.to_flask_config())
    
    # 2. Инициализация расширений
    init_logging(app)
    init_semantic_core(app)
    
    # 3. Регистрация blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(search_bp)
    
    return app
```

**Преимущества Factory:**

| Аспект | Без Factory | С Factory |
|--------|-------------|-----------|
| Тестирование | Сложно изолировать | Каждый тест — новый app |
| Конфигурация | Глобальные переменные | Per-instance config |
| Blueprints | Race conditions | Чистая регистрация |

---

## 🔧 Конфигурация через Pydantic Settings

Flask использует словари для конфигурации, но мы хотим **type safety** и **валидацию**:

```python
class FlaskAppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLASK_",  # FLASK_SECRET_KEY, FLASK_PORT, etc.
        env_file=".env",
    )
    
    secret_key: str = "dev-secret-key-change-in-production"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 5000
    upload_folder: Path = Path("uploads")
    max_content_length: int = 50 * 1024 * 1024  # 50MB
    
    def to_flask_config(self) -> dict:
        """Преобразовать в формат Flask."""
        return {
            "SECRET_KEY": self.secret_key,
            "DEBUG": self.debug,
            "UPLOAD_FOLDER": str(self.upload_folder),
            "MAX_CONTENT_LENGTH": self.max_content_length,
        }
```

**Приоритет источников:**

```
1. Environment Variables (FLASK_SECRET_KEY)
       ↓
2. .env File
       ↓
3. Default Values в классе
```

---

## 💉 Dependency Injection

### Паттерн: Flask Extensions

Flask имеет встроенный механизм для DI — `app.extensions`:

```python
def init_semantic_core(app: Flask) -> None:
    """Инициализировать SemanticCore и сохранить в extensions."""
    
    # Загрузка конфига semantic_core
    config = get_config()  # SemanticConfig
    
    # Инициализация компонентов
    db = init_peewee_database(config.db_path)
    embedder = GeminiEmbedder(api_key=config.require_api_key())
    store = PeeweeVectorStore(database=db)
    splitter = SmartSplitter(parser=MarkdownNodeParser())
    
    # Сборка ядра
    core = SemanticCore(
        embedder=embedder,
        store=store,
        splitter=splitter,
    )
    
    # Сохранение в extensions
    app.extensions["semantic_core"] = core
    app.extensions["semantic_config"] = config
```

### Использование в routes

```python
from flask import current_app

@main_bp.route("/search")
def search():
    core = current_app.extensions["semantic_core"]
    results = core.search(request.args.get("q"))
    return render_template("results.html", results=results)
```

**Почему Flask Extensions, а не свой DI-контейнер?**

| Подход | Плюсы | Минусы |
|--------|-------|--------|
| Flask Extensions | Zero dependencies, стандарт Flask | Простой словарь |
| Flask-Injector | Type hints, autowiring | Лишняя зависимость |
| Dependency-Injector | Полноценный DI | Overkill для MVP |

---

## 🛡 Graceful Degradation

Приложение должно работать даже без `GEMINI_API_KEY`:

```python
def init_semantic_core(app: Flask) -> None:
    config = get_config()
    
    # Embedder требует API key
    try:
        api_key = config.require_api_key()
        embedder = GeminiEmbedder(api_key=api_key)
    except ValueError:
        logger.warning("⚠️ API ключ не настроен. Поиск будет ограничен.")
        embedder = None
    
    # Store всегда доступен (локальная SQLite)
    store = PeeweeVectorStore(database=db)
    
    # Core создаётся только если есть embedder
    app.extensions["semantic_core"] = SemanticCore(...) if embedder else None
    app.extensions["semantic_store"] = store  # Всегда доступен
```

**Health endpoint отражает статус:**

```python
@main_bp.route("/health")
def health():
    core = current_app.extensions.get("semantic_core")
    return {
        "status": "ok" if core else "degraded",
        "semantic_core": "available" if core else "unavailable",
    }
```

---

## 📊 HTTP Logging Middleware

Интеграция SemanticLogger в HTTP слой:

```python
def _register_request_logging(app: Flask) -> None:
    
    @app.before_request
    def log_request_start():
        g.request_start_time = time.perf_counter()
    
    @app.after_request
    def log_request_end(response):
        duration_ms = (time.perf_counter() - g.request_start_time) * 1000
        
        # Эмодзи по статусу
        if response.status_code >= 500:
            emoji = "🔥"  # Server error
        elif response.status_code >= 400:
            emoji = "⚠️"  # Client error
        elif duration_ms < 100:
            emoji = "⚡"  # Fast response
        else:
            emoji = "🌐"  # Normal HTTP
        
        logger.info(f"{emoji} [{request.method}] {request.path} → {response.status_code} ({duration_ms:.1f}ms)")
        
        return response
```

**Примеры логов:**

```
⚡ [GET] / → 200 (12.3ms)
🌐 [POST] /search → 200 (156.7ms)
⚠️ [GET] /unknown → 404 (8.1ms)
🔥 [POST] /upload → 500 (234.5ms)
```

---

## 🎨 UI Stack

### Bootstrap 5.3 с Auto Dark Mode

```html
<html data-bs-theme="auto">
<script>
    // Автоопределение системной темы
    const getPreferredTheme = () => {
        const stored = localStorage.getItem('theme');
        if (stored) return stored;
        return window.matchMedia('(prefers-color-scheme: dark)').matches 
            ? 'dark' : 'light';
    };
    
    document.documentElement.setAttribute('data-bs-theme', getPreferredTheme());
</script>
```

### HTMX для интерактивности

```html
<!-- Поиск без перезагрузки страницы -->
<input 
    type="search"
    name="q"
    hx-get="/search"
    hx-target="#results"
    hx-trigger="keyup changed delay:300ms"
>
<div id="results">
    <!-- Результаты вставляются сюда -->
</div>
```

**Преимущества HTMX:**

- Минимум JavaScript кода
- Серверный рендеринг (SEO-friendly)
- Прогрессивное улучшение
- Размер: 14KB (vs React 42KB)

---

## 🗂 Структура проекта

```
examples/flask_app/
├── app/
│   ├── __init__.py         # create_app() factory
│   ├── config.py           # FlaskAppConfig (Pydantic)
│   ├── extensions.py       # SemanticCore DI
│   ├── logging.py          # HTTP middleware
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py         # Dashboard, /health
│   │   ├── search.py       # /search (Phase 12.2)
│   │   ├── ingest.py       # /upload (Phase 12.3)
│   │   └── chat.py         # /chat (Phase 12.4)
│   ├── templates/
│   │   ├── base.html       # Bootstrap 5.3 + HTMX
│   │   ├── index.html      # Dashboard
│   │   └── ...
│   └── static/
│       ├── css/
│       └── js/
├── tests/                  # pytest-flask
├── uploads/                # Загруженные файлы
├── run.py                  # Entry point
└── pyproject.toml
```

---

## 🧪 Тестирование

### pytest-flask fixtures

```python
# tests/conftest.py
@pytest.fixture
def app():
    """Flask app с тестовой конфигурацией."""
    from app import create_app
    
    return create_app(config={
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
    })

@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()
```

### Пример теста

```python
def test_health_endpoint(client):
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data
    assert data["semantic_core"] in ["available", "unavailable"]
```

---

## 🔗 Связь с другими эпизодами

| Эпизод | Связь |
|--------|-------|
| [40. Unified Configuration](40_unified_configuration.md) | SemanticConfig загружается через `get_config()` |
| [44. RAG Engine](44_rag_engine_architecture.md) | Flask /chat использует RAGEngine |
| [35. Semantic Logging](35_semantic_logging.md) | HTTP middleware интегрирует SemanticLogger |
| [41. CLI Architecture](41_cli_architecture.md) | Flask переиспользует те же компоненты |

---

## 📚 Итоги

**Flask + SemanticCore** = мощная комбинация для создания Knowledge Base:

1. **Application Factory** — тестируемость и модульность
2. **Pydantic Settings** — type-safe конфигурация
3. **Flask Extensions** — стандартный DI без зависимостей
4. **Graceful Degradation** — работает даже без API key
5. **HTMX + Bootstrap 5.3** — современный UI минимумом JS

**Следующие шаги:**

- Phase 12.1: Search Query Cache
- Phase 12.2: Search Interface
- Phase 12.3: Document Upload
- Phase 12.4: RAG Chat

---

**← [Вернуться к оглавлению](00_overview.md)**
