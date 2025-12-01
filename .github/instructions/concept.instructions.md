---
applyTo: "**"
name: "ConceptInstructions"
description: "Концепция и архитектура проекта Semantic Core"
---

# 🧠 Semantic Core Library: Concept & Architecture

Production-ready библиотека для локального семантического поиска и мультимодального анализа.

**Философия:**
* **Local-First:** SQLite (`vec0` + `fts5`) вместо векторных БД. Zero-dependency (без Docker).
* **Gemini-Powered:** Интеллект через Google Gemini (Text/Vision), экономия через **Batch API**.
* **Modular:** SOLID архитектура, готовая к замене компонентов (ORM, AI Provider).

### 🔍 Режимы Поиска
Библиотека реализует три стратегии через единый интерфейс:
1.  **Vector Search:** Семантический поиск по смыслу (через `sqlite-vec`).
2.  **Exact/SQL Search:** Жесткая фильтрация по метаданным и FTS5 (ключевые слова).
3.  **Hybrid Search (RRF):** Объединение результатов 1 и 2 через Reciprocal Rank Fusion.

### 🛠 Стек и Зависимости
**ВАЖНО:** Используй **Context7 ID** для поиска документации при сомнениях.

| Пакет | Назначение | Context7 ID |
| :--- | :--- | :--- |
| `peewee` | ORM, адаптеры, расширения SQLite | `/coleifer/peewee` |
| `sqlite-vec` | Векторный движок (C-extension) | `/asg017/sqlite-vec` |
| `google-genai` | SDK для Embeddings, Vision, Batch | `/googleapis/python-genai` |
| `markdown-it-py` | AST-парсинг Markdown | `/executablebooks/markdown-it-py` |
| `pydantic` | Валидация DTO и настроек | `/pydantic/pydantic` |

### 🗺 Дорожная Карта
Детали реализации смотри в соответствующих файлах планов:

* **Phase 1: Core & Contracts** (`plan_phase_1.md`) — DTO, Интерфейсы, Базовая структура.
* **Phase 2: Storage Layer** (`plan_phase_2.md`) — Peewee Adapter, Parent-Child схема.
* **Phase 3: Integration API** (`plan_phase_3.md`) — Дескрипторы `SemanticIndex`, DocumentBuilder.
* **Phase 3.1: Testing** (`plan_phase_3.1.md`) — Моки, Фикстуры, Unit/Integration тесты.
* **Phase 4: Smart Markdown** (`plan_phase_4.md`) — AST парсинг, Иерархический контекст.
* **Phase 5: Async Batching** (`plan_phase_5.md`) — Очереди `BatchJob`, отложенная обработка.
* **Phase 6: Multimodality** (`plan_phase_6.md`) — Vision стратегии, OCR, Media Processing.

### 📂 Структура Проекта
```text
semantic_core/
├── __init__.py               # Фасад (SemanticFactory)
├── domain/                   # DTO (Document, Chunk, MediaResource)
├── interfaces/               # Контракты (VectorStore, Embedder, Splitter)
├── integrations/             # Дескрипторы для ORM (SemanticIndex)
├── infrastructure/           # Реализация (Adapters)
│   ├── google/               # Gemini Client, Batching
│   ├── storage/              # Peewee Adapter
│   └── media/                # Vision Wrappers
├── processing/               # Логика (Business Logic)
│   ├── parsers/              # MarkdownNodeParser (AST)
│   └── context/              # ContextStrategies
└── pipeline.py               # Orchestrator