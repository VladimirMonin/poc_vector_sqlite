---
applyTo: "**"
name: "ConceptInstructions"
description: "Концепция и архитектура проекта Semantic Core"
---

# 🧠 Semantic Core Library: Concept & Architecture

Production-ready библиотека для локального семантического поиска и мультимодального анализа.

**Философия:**

- **Local-First:** SQLite (`vec0` + `fts5`) вместо векторных БД. Zero-dependency (без Docker).
- **Gemini-Powered:** Интеллект через Google Gemini (Text/Vision/Audio), экономия через **Batch API**.
- **Modular:** SOLID архитектура, готовая к замене компонентов (ORM, AI Provider).

### 🔍 Режимы Поиска

1.  **Vector Search:** Семантический поиск по смыслу (через `sqlite-vec`).
2.  **Exact/SQL Search:** Жесткая фильтрация по метаданным и FTS5.
3.  **Hybrid Search (RRF):** Объединение 1 и 2 через Reciprocal Rank Fusion.

### 🛠 Стек и Зависимости

**ВАЖНО:** Используй **Context7 ID** для поиска документации при сомнениях.

| Пакет            | Назначение                        | Context7 ID                       |
| :--------------- | :-------------------------------- | :-------------------------------- |
| `peewee`         | ORM, адаптеры, расширения SQLite  | `/coleifer/peewee`                |
| `sqlite-vec`     | Векторный движок (C-extension)    | `/asg017/sqlite-vec`              |
| `google-genai`   | SDK для Embeddings, Vision, Batch | `/googleapis/python-genai`        |
| `pydantic`       | Валидация DTO и настроек          | `/pydantic/pydantic`              |
| `markdown-it-py` | AST-парсинг Markdown              | `/executablebooks/markdown-it-py` |
| `Pillow`         | Обработка изображений             | `/python-pillow/pillow`           |
| `pydub`          | Извлечение/оптимизация аудио      | `/jiaaro/pydub`                   |
| `imageio[pyav]`  | Извлечение кадров из видео        | `/imageio/imageio`                |
| `rich`           | Console logging с цветами         | `/textualize/rich`                |
| `typer`          | CLI framework для команд          | `/fastapi/typer`                  |
| `pytest`         | Тестирование и фикстуры           | `/pytest-dev/pytest`              |
| `python-dotenv`  | Загрузка .env переменных          | `/theskumar/python-dotenv`        |

### 🗺 Дорожная Карта

[full_plan.md](doc/ideas/full_plan.md) — общий план. Детали в `doc/ideas/phase_N/`.

- **Phase 1-5:** Core, Storage, Integration, Markdown, Batching — {DONE}
- **Phase 6:** Multimodality (Images/Audio/Video) — {DONE}
- **Phase 7:** Logging Core Infrastructure — {DONE}
- **Phase 8:** CLI & Configuration — {DONE}
- **Phase 9:** RAG Integration — {DONE}
- **Phase 10:** Batch API Real Implementation — {DONE}
- **Phase 11:** Documentation & Diagrams — {DONE}
- **Phase 12:** Flask Web Application — {IN ANOTHER BRANCH. IN PAUSE}
  - **12.0:** App Skeleton, DI, Logging, Dashboard — {DONE}
  - **12.1:** Search Query Cache — {CURRENT}
  - **12.2-12.5:** Search UI, Ingest, Chat, Polish — {TODO}
- **Phase 13:** Total Visual Check & Audit Tools — {DONE}
- **Phase 14:** Media Content Crisis — {DONE}
- **Phase 15:** Optional Dependencies & Modular Extras — {DONE}
- **Phase 16:** Debug Observatory & Multi-Provider Inspection — {IN PROGRESS}
  - **16.0:** Inspector Core — {CURRENT}
  - **16.1:** CLI Inspect Command
  - **16.2:** Multi-Provider Snapshots
  - **16.3:** Comparison & Diff Engine
  - **16.4:** Interactive Mode
  - **16.5:** Golden Files Testing

### 🌐 Flask App (`examples/flask_app/`)

Веб-интерфейс для SemanticCore. Стек: Flask 3 + Bootstrap 5.3 + HTMX + Pydantic Settings.

| Компонент | Файл                 | Назначение                        |
| --------- | -------------------- | --------------------------------- |
| Factory   | `app/__init__.py`    | `create_app()` с Pydantic config  |
| DI        | `app/extensions.py`  | `app.extensions['semantic_core']` |
| Config    | `app/config.py`      | `FlaskAppConfig` (FLASK\_ prefix) |
| HTTP Logs | `app/logging.py`     | Middleware с эмодзи (🌐⚡⚠️🔥)    |
| Dashboard | `app/routes/main.py` | `/`, `/health`                    |

### 📂 Структура Проекта

```text
semantic_core/
├── domain/                   # DTO (Document, Chunk, SearchResult, MediaAnalysisResult)
├── interfaces/               # Контракты (VectorStore, Embedder, Splitter, LLMProvider)
├── integrations/             # ORM интеграции (SemanticIndex, PeeweeAdapter)
│   └── peewee/               # PeeweeAdapter, SearchProxy
├── core/                     # Высокоуровневая оркестрация
│   ├── rag.py                # RAGEngine — вопрос-ответ с источниками
│   ├── media_queue.py        # MediaQueueProcessor
│   ├── factory.py            # ComponentFactory для создания провайдеров
│   ├── context/              # Стратегии сжатия контекста чата
│   └── observatory/          # 🆕 Debug Observatory (Phase 16)
│       ├── inspector.py      # ProviderInspector — перехват данных
│       ├── recorder.py       # PipelineRecorder — запись шагов
│       ├── snapshot.py       # SnapshotManager — сохранение артефактов
│       └── reporters/        # Экспорт отчётов
│           ├── console.py    # Rich TUI для терминала
│           ├── markdown.py   # Markdown отчёты
│           ├── json.py       # JSON dumps
│           └── diff.py       # Сравнение снимков
├── cli/                      # CLI приложение (Typer + Rich)
│   ├── app.py                # Точка входа CLI
│   ├── commands/             # Команды
│   │   ├── ingest.py         # semantic ingest
│   │   ├── search.py         # semantic search
│   │   ├── chat.py           # semantic chat
│   │   ├── inspect.py        # 🆕 semantic inspect (Phase 16)
│   │   ├── compare.py        # 🆕 semantic compare (Phase 16)
│   │   └── golden.py         # 🆕 semantic golden (Phase 16)
│   ├── chat/                 # Интерактивный RAG-чат
│   │   └── slash/            # Slash-команды (/search, /sources, /model)
│   ├── console.py            # Rich console
│   └── ui/                   # UI компоненты
├── utils/                    # Утилиты
│   └── logger/               # Semantic logging (TRACE, эмодзи, bind, secrets)
├── infrastructure/
│   ├── gemini/               # Gemini интеграции
│   │   ├── embedder.py       # Embeddings API (gemini-embedding-001)
│   │   ├── image_analyzer.py # Vision API
│   │   ├── audio_analyzer.py # Audio API
│   │   ├── video_analyzer.py # Video (frames + audio)
│   │   ├── rate_limiter.py   # Token Bucket RPM control
│   │   ├── resilience.py     # Retry, backoff, error classification
│   │   └── batching.py       # Batch API client (50% экономия)
│   ├── llm/                  # LLM провайдеры
│   │   └── gemini_llm.py     # GeminiLLMProvider для RAG
│   ├── media/utils/          # Утилиты обработки медиа
│   │   ├── images.py         # Pillow: resize, optimize
│   │   ├── audio.py          # pydub: extract, compress
│   │   ├── video.py          # imageio: frame extraction
│   │   ├── tokens.py         # Token estimation
│   │   └── files.py          # Path resolution, MIME detection
│   ├── storage/peewee/       # PeeweeVectorStore, MediaTaskModel
│   └── text_processing/      # SimpleSplitter (legacy)
├── processing/               # Парсинг и обогащение
│   ├── parsers/              # MarkdownNodeParser (AST)
│   ├── splitters/            # SmartSplitter
│   ├── context/              # HierarchicalContextStrategy
│   └── enrichers/            # MarkdownAssetEnricher
├── config.py                 # SemanticConfig (Pydantic Settings, TOML)
├── batch_manager.py          # Очередь batch-задач
└── pipeline.py               # SemanticCore orchestrator

tests/                        # 645+ unit-тестов
├── conftest.py               # Все фикстуры проекта
├── unit/                     # Изолированные unit-тесты
│   ├── core/                 # RAGEngine, BatchManager, ComponentFactory
│   ├── infrastructure/       # Gemini, LLM, Media utils
│   ├── cli/                  # CLI команды, конфигурация
│   └── processing/           # Parsers, Context, Splitters
├── integration/              # Тесты с реальной БД
│   ├── media/                # Pipeline + QueueProcessor
│   ├── search/               # Гибридный поиск
│   └── core/                 # 🆕 ComponentFactory integration tests
├── e2e/                      # End-to-End с реальными API
│   └── audit/                # 🆕 PipelineInspector e2e tests (Phase 13)
└── fixtures/                 # Тестовые данные

docs/                         # Документация проекта
└── diagrams/                 # PlantUML диаграммы
    ├── *.puml                # Исходники диаграмм
    └── images/               # Отрендеренные .webp
```

**Подробнее о тестах:** [tests/README.md](tests/README.md)  
**Подробнее о логировании:** [semantic_core/utils/logger/README.md](semantic_core/utils/logger/README.md)

### 📚 Документация и Тестирование

**📖 Точки входа в документацию:**

| Ресурс                     | Путь                                                               | Описание                         |
| -------------------------- | ------------------------------------------------------------------ | -------------------------------- |
| **Публичная документация** | [docs/README.md](docs/README.md)                                   | Гайды, концепции, справочники    |
| **Архитектурный сериал**   | [doc/architecture/00_overview.md](doc/architecture/00_overview.md) | 74 статьи, организованы по фазам |
| **Планы и отчёты**         | [doc/ideas/](doc/ideas/)                                           | Технические отчёты по фазам      |

> 📂 **Новая структура:** Архитектурный сериал реорганизован в папки по фазам (`phase_0_legacy/`, `phase_1_solid/`, ..., `phase_14_media_crisis/`). Каждая фаза имеет README с описанием и ссылками на статьи.

> ⚠️ `phase_0_legacy/` содержит старую архитектуру до SOLID рефакторинга.

**🖥️ CLI и интерактивный чат:**

```bash
# Основные команды
semantic ingest <path>          # Загрузить документы
semantic search "query"         # Поиск по базе
semantic chat                   # Интерактивный RAG-чат

# Slash-команды в чате
/search query    # Поиск без LLM
/sources         # Показать источники
/model           # Сменить модель
/clear           # Очистить историю
```

**Workflow разработки:**

1. Реализуем функциональность текущей фазы
2. Коммиты делаем походу разработки по правилам из инструкций. Пуш не делаем!
3. Пишем тесты в пакете `tests/` (pytest). Тесты у нас запускаются из корня проекта.
4. Когда всё работает и протестировано — заканчиваем фазу
5. Вчитываем правила оформления архитектурного сериала: `doc\architecture\00_documentation_style_guide.md`
5. Пишем статьи в `doc/architecture/phase_N/` по завершённой фазе
6. Следуем стайл-гайду: минимум кода, максимум объяснений и диаграмм
7. Обновляем README фазы (`phase_N/README.md`) со ссылками на новые статьи
