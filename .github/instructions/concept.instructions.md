---
applyTo: "**"
name: "ConceptInstructions"
description: "Концепция и архитектура проекта Semantic Core"
---

# 🧠 Semantic Core Library: Concept & Architecture

Production-ready библиотека для локального семантического поиска и мультимодального анализа.

**Философия:**

- **Local-First:** SQLite (`vec0` + `fts5`) вместо векторных БД. Zero-dependency (без Docker).
- **Gemini-Powered:** Интеллект через Google Gemini (Text/Vision), экономия через **Batch API**.
- **Modular:** SOLID архитектура, готовая к замене компонентов (ORM, AI Provider).

### 🔍 Режимы Поиска

Библиотека реализует три стратегии через единый интерфейс:

1.  **Vector Search:** Семантический поиск по смыслу (через `sqlite-vec`).
2.  **Exact/SQL Search:** Жесткая фильтрация по метаданным и FTS5 (ключевые слова).
3.  **Hybrid Search (RRF):** Объединение результатов 1 и 2 через Reciprocal Rank Fusion.

### 🛠 Стек и Зависимости

**ВАЖНО:** Используй **Context7 ID** для поиска документации при сомнениях.

| Пакет            | Назначение                        | Context7 ID                       |
| :--------------- | :-------------------------------- | :-------------------------------- |
| `peewee`         | ORM, адаптеры, расширения SQLite  | `/coleifer/peewee`                |
| `sqlite-vec`     | Векторный движок (C-extension)    | `/asg017/sqlite-vec`              |
| `google-genai`   | SDK для Embeddings, Vision, Batch | `/googleapis/python-genai`        |
| `pydantic`       | Валидация DTO и настроек          | `/pydantic/pydantic`              |
| `markdown-it-py` | AST-парсинг Markdown              | `/executablebooks/markdown-it-py` |

### 🗺 Дорожная Карта

Общая дорожна карта тут:
[full_plan.md](doc/ideas/full_plan.md)

Детали реализации смотри в соответствующих файлах планов в подпапках.:

- **Phase 1: Core & Contracts** (`plan_phase_1.md`) — DTO, Интерфейсы, Базовая структура. {DONE}
- **Phase 2: Storage Layer** (`plan_phase_2.md`) — Peewee Adapter, Parent-Child схема. {DONE}
- **Phase 3: Integration API** (`plan_phase_3.md`) — Дескрипторы `SemanticIndex`, DocumentBuilder. {DONE}
- **Phase 3.1: Testing** (`plan_phase_3.1.md`) — Моки, Фикстуры, Unit/Integration тесты. {DONE}
- **Phase 4: Smart Markdown** (`plan_phase_4.md`) — AST парсинг, Иерархический контекст. {WE ARE HERE}
- **Phase 5: Async Batching** (`plan_phase_5.md`) — Очереди `BatchJob`, отложенная обработка. {PLANNED}
- **Phase 6: Multimodality** (`plan_phase_6.md`) — Vision стратегии, OCR, Media Processing. {PLANNED}

### 📂 Структура Проекта

```text
semantic_core/
├── __init__.py               # Фасад (SemanticFactory)
├── domain/                   # DTO (Document, Chunk, SearchResult)
├── interfaces/               # Контракты (VectorStore, Embedder, Splitter, Context)
├── integrations/             # Интеграции с ORM
│   ├── base.py               # SemanticIndex (descriptor), DocumentBuilder
│   ├── peewee/               # PeeweeAdapter (method patching)
│   └── search_proxy.py       # SearchProxy для семантического поиска
├── infrastructure/           # Реализация (Adapters)
│   ├── gemini/               # GeminiEmbedder, Batch API
│   ├── storage/peewee/       # PeeweeVectorStore, Models
│   └── text_processing/      # SimpleSplitter, BasicContext
├── processing/               # Логика (Business Logic) [PLANNED]
│   ├── parsers/              # MarkdownNodeParser (AST)
│   └── context/              # ContextStrategies
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
