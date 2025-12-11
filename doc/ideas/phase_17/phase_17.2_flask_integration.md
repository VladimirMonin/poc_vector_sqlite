# Phase 17.2: Flask Integration Guide

> Детальный гайд по интеграции SemanticCore в Flask приложения

---

## 📦 Статус

- **Фаза:** 17.2
- **Зависит от:** Phase 15.4 (ComponentFactory), Phase 12 (Flask App)
- **Блокирует:** 17.6 (Django Integration)
- **Приоритет:** 🔥 Критический
- **Оценка:** 3-4 дня

---

## 🎯 Проблема

**Текущая ситуация:**

1. Flask app существует в `examples/flask_app/` (Phase 12)
2. Flask app **НЕ обновлён** под Phase 15 (multi-provider архитектура)
3. **Документации нет вообще** — пользователи не знают как интегрировать SemanticCore в Flask

**Разрыв:**

| Аспект | Flask App (текущий) | Phase 15 архитектура |
|--------|---------------------|---------------------|
| Инициализация | Hardcoded Gemini | ComponentFactory |
| Конфигурация | Manual Pydantic | Unified SemanticConfig |
| DI | app.extensions dict | Фабричный паттерн |
| Локальные модели | ❌ Не поддерживается | ✅ Полная поддержка |

**Последствия:**

- Невозможно использовать локальные модели в Flask app
- Дублирование кода (extensions.py создаёт компоненты вручную)
- Нет документации для новых пользователей
- Невозможно расширить на Django/FastAPI без примера

---

## 💡 Решение

### Этап 1: Миграция Flask App (СНАЧАЛА)

**Обновить код Flask приложения** под Phase 15 архитектуру.

#### 1.1. Обновить `examples/flask_app/app/extensions.py`

**До (Phase 12):**

```python
def init_semantic_core(app: Flask) -> None:
    # Hardcoded Gemini providers
    embedder = GeminiEmbedder(
        api_key=app.config["FLASK_GEMINI_API_KEY"],
        model_name="text-embedding-004"
    )
    
    audio_analyzer = GeminiAudioAnalyzer(...)
    image_analyzer = GeminiImageAnalyzer(...)
    
    # Manual assembly
    core = SemanticCore(
        embedder=embedder,
        store=store,
        # ...
    )
```

**После (Phase 15):**

```python
from semantic_core import get_config
from semantic_core.core.factory import ComponentFactory

def init_semantic_core(app: Flask) -> None:
    # Загружаем unified конфигурацию
    semantic_config = get_config()
    
    # Создаём через фабрику (поддерживает все провайдеры)
    embedder = ComponentFactory.create_embedder(semantic_config)
    llm = ComponentFactory.create_llm(semantic_config)
    transcriber = ComponentFactory.create_transcriber(semantic_config)
    vision_analyzer = ComponentFactory.create_vision_analyzer(semantic_config)
    
    # Собираем SemanticCore
    core = ComponentFactory.create_semantic_core(semantic_config)
    
    # Сохраняем в Flask extensions
    app.extensions['semantic_core'] = core
    app.extensions['semantic_config'] = semantic_config
```

#### 1.2. Обновить `examples/flask_app/app/config.py`

**Добавить поддержку FLASK_ prefix для SemanticConfig:**

```python
from semantic_core.config import SemanticConfig

class FlaskAppConfig(BaseSettings):
    # Flask специфичные настройки
    upload_folder: Path = Path("uploads")
    max_content_length: int = 16 * 1024 * 1024  # 16MB
    
    # SemanticCore конфигурация (наследуем)
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    
    model_config = SettingsConfigDict(
        env_prefix="FLASK_",
        env_nested_delimiter="__"
    )
```

#### 1.3. Создать `examples/flask_app/semantic.toml`

```toml
# Flask App Configuration

[defaults]
embedding_provider = "local"      # Локальные embeddings
llm_provider = "gemini"           # Облачный LLM (качество)
transcription_provider = "whisper" # Локальная транскрипция
vision_provider = "gemini"        # Облачное Vision

[providers.local]
device = "mps"                    # Apple Silicon
embedding_model = "qwen3-embedding"
whisper_model = "base"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
llm_model = "gemini-2.0-flash"

[database]
db_path = "flask_semantic.db"
```

### Этап 2: Документация (ПОТОМ)

После миграции кода создать документы.

#### 2.1. `docs/guides/integrations/flask.md`

**Назначение:** Полный гайд по интеграции в Flask.

**Структура:**

```markdown
# Flask Integration Guide

## Что получим
- Flask app с SemanticCore
- Поддержка локальных моделей
- Production-ready конфигурация

## Архитектура интеграции

### Синхронная природа SemanticCore
⚠️ SemanticCore синхронный, Flask может быть async

### Application Factory Pattern
def create_app(config_name='default'):
    app = Flask(__name__)
    init_semantic_core(app)
    return app

### Dependency Injection через app.extensions
app.extensions['semantic_core']  # SemanticCore instance

## Установка

### Зависимости
poetry add semantic-core[local-embeddings,whisper]
poetry add flask pydantic-settings

### Структура проекта
flask_app/
├── app/
│   ├── __init__.py        # create_app()
│   ├── config.py          # FlaskAppConfig
│   ├── extensions.py      # init_semantic_core()
│   └── routes/
│       ├── main.py        # Dashboard
│       ├── search.py      # Search API
│       └── ingest.py      # Upload & ingest
├── semantic.toml          # SemanticCore config
├── .env                   # API keys
└── run.py                 # Entry point

## Конфигурация

### semantic.toml (SemanticCore)
[defaults]
embedding_provider = "local"
llm_provider = "gemini"

### .env (API keys + Flask)
GEMINI_API_KEY=your_key
FLASK_SECRET_KEY=random_string
FLASK_DEBUG=False

### config.py (Flask settings)
class FlaskAppConfig(BaseSettings):
    upload_folder: Path = Path("uploads")
    max_content_length: int = 16 * 1024 * 1024
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)

## Инициализация SemanticCore

### extensions.py — DI контейнер
```python
from semantic_core import get_config
from semantic_core.core.factory import ComponentFactory

def init_semantic_core(app: Flask):
    config = get_config()
    core = ComponentFactory.create_semantic_core(config)
    
    app.extensions['semantic_core'] = core
    app.extensions['semantic_config'] = config
```

### __init__.py — Factory
```python
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    init_semantic_core(app)  # Инициализация
    
    register_blueprints(app)
    return app
```

## Использование в routes

### Доступ к SemanticCore
```python
from flask import Blueprint, current_app

bp = Blueprint('search', __name__)

@bp.route('/search')
def search():
    core = current_app.extensions['semantic_core']
    results = core.search(query, limit=10)
    return jsonify([r.to_dict() for r in results])
```

### Ingest endpoint
```python
@bp.route('/ingest', methods=['POST'])
def ingest():
    file = request.files['file']
    content = file.read().decode('utf-8')
    
    core = current_app.extensions['semantic_core']
    doc = core.ingest(content, metadata={'filename': file.filename})
    
    return jsonify({'doc_id': doc.doc_id, 'chunks': len(doc.chunks)})
```

### RAG endpoint
```python
@bp.route('/chat', methods=['POST'])
def chat():
    question = request.json['question']
    history = request.json.get('history', [])
    
    rag_engine = current_app.extensions['rag_engine']
    response = rag_engine.ask(question, chat_history=history)
    
    return jsonify({
        'answer': response.answer,
        'sources': [s.to_dict() for s in response.sources]
    })
```

## Production чек-лист

### SQLite настройки
- ✅ WAL mode включён (db_init.py)
- ✅ PRAGMA journal_mode=WAL
- ✅ PRAGMA busy_timeout=5000

### Безопасность
- ✅ API keys через environment variables
- ✅ FLASK_SECRET_KEY случайный
- ✅ max_content_length ограничен

### Логирование
- ✅ Semantic logging настроен
- ✅ HTTP middleware логирует запросы
- ✅ Errors в stderr, info в stdout

### Мониторинг
- ✅ /health endpoint
- ✅ DB metrics через PRAGMA
- ✅ Error tracking (Sentry/etc)

## Переключение провайдеров

### Сценарий 1: Локальная разработка (бесплатно)
[defaults]
embedding_provider = "local"
llm_provider = "ollama"

### Сценарий 2: Production (качество)
[defaults]
embedding_provider = "gemini"
llm_provider = "gemini"

### Сценарий 3: Гибридный (экономия)
[defaults]
embedding_provider = "local"  # Часто используется
llm_provider = "gemini"       # Редко, но качество

## Troubleshooting

### Ошибка: ImportError: MLX dependencies not installed
pip install semantic-core[local-embeddings]

### Ошибка: Database is locked
# Включить WAL mode в db_init.py

### Медленный ingest
# Использовать batch API (Gemini)
# Или локальные embeddings (быстрее)

## Примеры запросов

### curl examples
# Search
curl http://localhost:5000/api/search?q=embeddings

# Ingest
curl -X POST -F "file=@doc.md" http://localhost:5000/api/ingest

# Chat
curl -X POST -H "Content-Type: application/json" \
  -d '{"question": "What are embeddings?"}' \
  http://localhost:5000/api/chat
```

---

#### 2.2. Обновить `docs/guides/integrations/architecture.md`

**Добавить секцию "Flask Pattern":**

```markdown
## Flask Integration Pattern

### Application Factory
```python
def create_app():
    app = Flask(__name__)
    init_semantic_core(app)  # DI injection
    return app
```

### Extensions Pattern
Flask использует `app.extensions` dict для DI:

```python
app.extensions['semantic_core'] = core
```

### Доступ в routes
```python
core = current_app.extensions['semantic_core']
```

### Lifecycle
1. create_app() создаёт Flask instance
2. init_semantic_core() создаёт SemanticCore (один раз)
3. Routes используют через current_app (thread-safe)
```

---

#### 2.3. Обновить `docs/guides/integrations/sync-nature.md`

**Добавить Flask пример:**

```markdown
## Flask (sync framework)

Flask **синхронный**, SemanticCore **синхронный** → ✅ Совместимость идеальная.

### Пример
```python
@app.route('/search')
def search():
    core = current_app.extensions['semantic_core']
    results = core.search(query)  # Блокирующий вызов — OK
    return jsonify(results)
```

### Async views (Flask 2.0+)
```python
@app.route('/search')
async def search():
    # ⚠️ SemanticCore синхронный!
    # Вариант 1: run_in_executor
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, core.search, query)
    
    # Вариант 2: просто sync вызов (блокирует event loop)
    results = core.search(query)  # ❌ Не рекомендуется
```
```

---

## 📂 Структура файлов после обновления

### Код (examples/flask_app/)

```
examples/flask_app/
├── app/
│   ├── __init__.py              # UPDATE: ComponentFactory
│   ├── config.py                # UPDATE: SemanticConfig integration
│   ├── extensions.py            # UPDATE: Фабричный паттерн
│   └── routes/
│       ├── main.py              # Без изменений (dashboard)
│       ├── search.py            # Без изменений (уже используют core)
│       └── ingest.py            # Без изменений
├── semantic.toml                # NEW: Конфигурация SemanticCore
├── .env.example                 # UPDATE: GEMINI_API_KEY (без FLASK_)
├── README.md                    # UPDATE: Обновить инструкции
└── requirements.txt             # UPDATE: semantic-core[local-embeddings]
```

### Документация (docs/)

```
docs/guides/integrations/
├── architecture.md              # UPDATE: Добавить Flask паттерн
├── flask.md                     # NEW: Полный Flask гайд
├── sync-nature.md               # UPDATE: Flask примеры
└── django.md                    # PLACEHOLDER (Phase 17.6)
```

---

## ✅ Acceptance Criteria

### Код Flask App

- [ ] `extensions.py` использует `ComponentFactory`
- [ ] `semantic.toml` создан с локальными моделями
- [ ] Все routes работают без изменений (backwards compatibility)
- [ ] Можно переключить `embedding_provider` через конфиг
- [ ] README.md обновлён с новыми инструкциями

### Документация

- [ ] `flask.md` покрывает все аспекты (setup, DI, routes, production)
- [ ] Примеры кода протестированы (копипаста работает)
- [ ] `architecture.md` объясняет Flask паттерн vs другие фреймворки
- [ ] `sync-nature.md` объясняет sync/async совместимость
- [ ] Все ссылки между документами работают

---

## 🎨 Стиль документации

### Практический фокус

Flask Integration — **практический гайд**, не концепты.

**Что включать:**

1. ✅ Полные примеры кода (copy-paste ready)
2. ✅ Чек-листы (Production checklist)
3. ✅ Troubleshooting секция
4. ✅ curl примеры для тестирования
5. ✅ Сценарии использования (dev/prod/hybrid)

**Чего избегать:**

1. ❌ Теоретические объяснения (есть в concepts/)
2. ❌ Дублирование кода из репо (ссылки вместо копий)
3. ❌ Избыточные диаграммы (только architecture pattern)

### Структура гайда

```markdown
## Что получим      # Goals
## Архитектура      # High-level pattern
## Установка        # Step-by-step setup
## Конфигурация     # Config examples
## Инициализация    # DI pattern
## Использование    # Route examples
## Production       # Checklist
## Troubleshooting  # Common errors
## Примеры          # curl/httpie commands
```

---

## 🔗 Связанные задачи

| Задача | Зависимость | Статус |
|--------|-------------|--------|
| Phase 12.0 | Flask App Skeleton | ✅ Done |
| Phase 15.4 | ComponentFactory | ✅ Done |
| **Phase 17.2** | **Flask Integration** | **🚧 Current** |
| Phase 17.6 | Django Integration | ⏳ Blocked by 17.2 |

---

## 🚀 План реализации

### Неделя 1: Миграция кода Flask App

**День 1-2: Обновление extensions.py**

1. Добавить `ComponentFactory` в imports
2. Заменить hardcoded Gemini на фабрику
3. Сохранить backwards compatibility (проверить routes)
4. Тестировать с Gemini провайдером (существующий)

**День 3: Тестирование локальных моделей**

5. Создать `semantic.toml` с `embedding_provider = "local"`
6. Установить `semantic-core[local-embeddings]`
7. Запустить Flask app и проверить ingest/search
8. Benchmark производительности (Gemini vs Local)

**День 4: Документация и cleanup**

9. Обновить `examples/flask_app/README.md`
10. Создать `.env.example` с правильными переменными
11. Обновить `requirements.txt` / `pyproject.toml`
12. Code review и cleanup

### Неделя 2: Документация пользователей

**День 5-6: Создание flask.md**

13. Написать все секции (setup, config, DI, routes, production)
14. Добавить примеры кода (протестированные)
15. Создать troubleshooting секцию
16. Добавить curl примеры

**День 7: Обновление связанных документов**

17. Обновить `architecture.md` (Flask паттерн)
18. Обновить `sync-nature.md` (Flask примеры)
19. Обновить `docs/README.md` (добавить ссылку на flask.md)

**День 8: Review и интеграция**

20. Проверить все ссылки
21. Spell check
22. Consistency check (термины, стиль)
23. Commit в Phase 17

---

## 🎯 Будущие расширения (Phase 17.6)

После завершения Flask Integration, паттерн можно использовать для **Django Integration**.

### Общий паттерн для фреймворков

```python
# 1. Application Factory
def create_app():
    # Framework-specific setup
    pass

# 2. DI через фабрику
def init_semantic_core(app):
    config = get_config()
    core = ComponentFactory.create_semantic_core(config)
    app.inject(core)  # Framework-specific DI

# 3. Доступ в views
def view(request):
    core = request.app.get_service('semantic_core')
```

### Django специфика (Phase 17.6)

```python
# settings.py
SEMANTIC_CONFIG = get_config()

# apps.py
class SemanticCoreConfig(AppConfig):
    def ready(self):
        self.semantic_core = ComponentFactory.create_semantic_core(...)

# views.py
from django.apps import apps
core = apps.get_app_config('semantic_core').semantic_core
```

**Структура документации готова к Django.**

---

## 📊 Метрики успеха

- **Миграция кода:** Flask app работает с локальными моделями ✅
- **Backwards compatibility:** Старые routes без изменений ✅
- **Документация:** Новый пользователь может настроить Flask за 30 минут ✅
- **Extensibility:** Паттерн легко адаптировать для Django ✅

---

**Статус:** 📝 Draft | **Автор:** GitHub Copilot | **Дата:** 11 декабря 2025
