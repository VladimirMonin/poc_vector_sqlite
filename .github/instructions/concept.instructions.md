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

### 🗺 Дорожная Карта

[full_plan.md](doc/ideas/full_plan.md) — общий план. Детали в `doc/ideas/phase_N/`.

- **Phase 1-5:** Core, Storage, Integration, Markdown, Batching — {DONE}
- **Phase 6:** Multimodality (Images/Audio/Video) — {DONE}
- **Phase 7.0:** Logging Core Infrastructure — {DONE}

### 📂 Структура Проекта

```text
semantic_core/
├── domain/                   # DTO (Document, Chunk, SearchResult, MediaAnalysisResult)
├── interfaces/               # Контракты (VectorStore, Embedder, Splitter)
├── integrations/             # ORM интеграции (SemanticIndex, PeeweeAdapter)
│   └── peewee/               # PeeweeAdapter, SearchProxy
├── core/                     # Высокоуровневая оркестрация
│   └── media_queue.py        # MediaQueueProcessor
├── utils/                    # Утилиты
│   └── logger/               # Semantic logging (TRACE, эмодзи, bind, secrets)
├── infrastructure/
│   ├── gemini/               # GeminiEmbedder, ImageAnalyzer, AudioAnalyzer, VideoAnalyzer
│   │   ├── embedder.py       # Embeddings API
│   │   ├── image_analyzer.py # Vision API
│   │   ├── audio_analyzer.py # Audio API
│   │   ├── video_analyzer.py # Video (frames + audio)
│   │   ├── rate_limiter.py   # Token Bucket RPM control
│   │   ├── resilience.py     # Retry, backoff, error classification
│   │   └── batching.py       # Batch API client
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
├── batch_manager.py          # Очередь batch-задач
└── pipeline.py               # SemanticCore orchestrator

tests/                        # 470+ тестов
├── conftest.py               # Все фикстуры проекта
├── unit/                     # Изолированные unit-тесты
│   ├── core/                 # BatchManager
│   ├── infrastructure/       # Gemini, Media utils
│   └── processing/           # Parsers, Context, Splitters
├── integration/              # Тесты с реальной БД
│   ├── media/                # Pipeline + QueueProcessor
│   └── search/               # Гибридный поиск
├── e2e/                      # End-to-End с реальными API
└── fixtures/                 # Тестовые данные
```

**Подробнее о тестах:** [tests/README.md](tests/README.md)  
**Подробнее о логировании:** [semantic_core/utils/logger/README.md](semantic_core/utils/logger/README.md)

### 📚 Документация и Тестирование

**Архитектурные документы:**

- [Оглавление документации](doc/architecture/00_overview.md) — обзор всех 38 концепций проекта
- [Стайл-гайд документации](doc/architecture/00_documentation_style_guide.md) — правила написания доков

**Workflow разработки:**

1. Реализуем функциональность текущей фазы
2. Коммиты делаем походу разработки по правилам из инструкций. Пуш не делаем!
3. Пишем тесты в пакете `tests/` (pytest). Тесты у нас запускаются из корня проекта.
4. Когда всё работает и протестировано — заканчиваем фазу
5. Пишем один или несколько файлов в `doc/architecture/` по завершённой фазе
6. Следуем стайл-гайду: минимум кода, максимум объяснений и диаграмм
7. Обновляем оглавление в `00_overview.md`
