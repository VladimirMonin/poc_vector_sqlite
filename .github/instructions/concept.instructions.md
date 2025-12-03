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

### 🗺 Дорожная Карта

[full_plan.md](doc/ideas/full_plan.md) — общий план. Детали в `doc/ideas/phase_N/`.

- **Phase 1-5:** Core, Storage, Integration, Markdown, Batching — {DONE}
- **Phase 6:** Multimodality (Images/Audio/Video) — {WE ARE HERE}

### 📂 Структура Проекта

```text
semantic_core/
├── domain/                   # DTO (Document, Chunk, SearchResult, MediaAnalysisResult)
├── interfaces/               # Контракты (VectorStore, Embedder, Splitter)
├── integrations/             # ORM интеграции (SemanticIndex, PeeweeAdapter)
├── infrastructure/
│   ├── gemini/               # GeminiEmbedder, ImageAnalyzer, AudioAnalyzer
│   ├── media/utils/          # image.py, audio.py, video.py
│   ├── storage/peewee/       # PeeweeVectorStore, MediaTaskModel
│   └── text_processing/      # SimpleSplitter, MarkdownNodeParser
├── processing/               # Parsers, ContextStrategies
├── batch_manager.py          # Очередь задач, RateLimiter
└── pipeline.py               # Orchestrator

tests/
├── conftest.py               # Fixtures (in-memory БД, моки)
├── unit/                     # Юнит-тесты (изолированные компоненты)
└── integration/              # Интеграционные тесты (end-to-end)

### 📚 Документация и Тестирование

**Архитектурные документы:**
- [Оглавление документации](doc/architecture/00_overview.md) — обзор всех концепций проекта
- [Стайл-гайд документации](doc/architecture/00_documentation_style_guide.md) — правила написания доков

**Workflow разработки:**
1. Реализуем функциональность текущей фазы
2. Коммиты делаем походу разработки по правилам из инструкций. Пуш не делаем!
3. Пишем тесты в пакете `tests/` (pytest). Тесты у нас запускаются из корня проекта.
4. Когда всё работает и протестировано — заканчиваем фазу
5. Пишем один или несколько файлов в `doc/architecture/` по завершённой фазе
6. Следуем стайл-гайду: минимум кода, максимум объяснений и диаграмм
7. Обновляем оглавление в `00_overview.md`
```
