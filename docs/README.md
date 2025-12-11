---
title: "Semantic Core Documentation"
description: "Документация библиотеки локального семантического поиска"
---

# 📚 Semantic Core

> Production-ready библиотека для локального семантического поиска и мультимодального анализа.
> SQLite + sqlite-vec + Gemini AI. Zero Docker. Local-first.

---

## 🚀 Быстрый старт

```bash
# Установка
poetry install

# API ключ
echo "GEMINI_API_KEY=your_key" > .env

# Индексация и поиск
semantic ingest ./docs/
semantic search "как работает гибридный поиск"
```

**[→ Полное руководство](guides/core/quickstart.md)**

---

## 📖 Концепции

Теоретические основы — что и почему.

| Документ | Описание | Сложность |
|----------|----------|-----------|
| [Эмбеддинги](concepts/01_embeddings.md) | Векторные представления текста, MRL размерности | 🟢 beginner |
| [Векторный поиск](concepts/02_vector_search.md) | sqlite-vec, косинусное расстояние | 🟢 beginner |
| [Гибридный поиск RRF](concepts/03_hybrid_rrf.md) | Vector + FTS5, Reciprocal Rank Fusion | 🟡 intermediate |
| [Chunking](concepts/04_chunking.md) | Стратегии нарезки, overlap, лимиты | 🟢 beginner |
| [Smart Parsing](concepts/05_smart_parsing.md) | AST Markdown, иерархия заголовков | 🟡 intermediate |
| [Batch Processing](concepts/06_batch_processing.md) | Google Batch API, 50% экономия | 🟡 intermediate |
| [Multimodal](concepts/07_multimodal.md) | Анализ изображений, аудио, видео | 🟡 intermediate |
| [RAG Architecture](concepts/08_rag_architecture.md) | Retrieval-Augmented Generation | 🟡 intermediate |
| [Observability](concepts/09_observability.md) | Логирование, TRACE уровень, секреты | 🟢 beginner |
| [Plugin System](concepts/10_plugin_system.md) | Интерфейсы, DI, расширяемость | 🔴 advanced |
| [Multi-Provider](concepts/11_multi_provider.md) | Gemini, OpenAI, Local, Ollama | 🟡 intermediate |
| [Debug Observatory](concepts/12_debug_observatory.md) | Инспекция pipeline, артефакты | 🟡 intermediate |

---

## 🛠️ Гайды

Практические руководства — как делать.

### Core

| Документ | Описание |
|----------|----------|
| [Quickstart](guides/core/quickstart.md) | Первые шаги за 5 минут |
| [Configuration](guides/core/configuration.md) | semantic.toml, env, иерархия |
| [CLI Usage](guides/core/cli-usage.md) | Команды ingest, search, chat |
| [RAG Chat](guides/core/rag-chat.md) | Интерактивный чат с базой знаний |
| [Media Processing](guides/core/media-processing.md) | Изображения, аудио, видео |
| [Model Configuration](guides/core/model-configuration.md) | Выбор моделей Gemini |

### Integrations

| Документ | Описание |
|----------|----------|
| [Sync Nature](guides/integrations/sync-nature.md) | ⚠️ Sync Core в async фреймворках |
| [Architecture](guides/integrations/architecture.md) | DI, Singleton, инициализация |
| [Peewee ORM](guides/integrations/peewee.md) | Нативная интеграция с Peewee |
| [Custom ORM](guides/integrations/custom-orm.md) | Blueprints для Django/SQLAlchemy |

### Extending

| Документ | Описание |
|----------|----------|
| [Custom LLM](guides/extending/custom-llm-provider.md) | OpenAI, Anthropic, Ollama |
| [Custom Embedder](guides/extending/custom-embedder.md) | OpenAI, Cohere, local |
| [Custom VectorStore](guides/extending/custom-vector-store.md) | ChromaDB, Qdrant, Pinecone |
| [MCP Server](guides/extending/mcp-server.md) | Model Context Protocol интеграция |

### Deployment

| Документ | Описание |
|----------|----------|
| [Checklist](guides/deployment/checklist.md) | Pre-deploy проверки |
| [Production](guides/deployment/production.md) | WAL mode, настройки, мониторинг |

---

## 📋 Справочник

Таблицы и списки для быстрого поиска.

| Документ | Описание |
|----------|----------|
| [Interfaces](reference/interfaces.md) | Все интерфейсы и их методы |
| [CLI Commands](reference/cli-commands.md) | Полный справочник команд |
| [Configuration](reference/configuration-options.md) | Все опции semantic.toml |
| [Chunk Types](reference/chunk-types.md) | TEXT, CODE, IMAGE_REF... |
| [Error Codes](reference/error-codes.md) | Ошибки и их решения |
| [Models](reference/models.md) | Gemini модели и размерности |

---

## 🎨 Диаграммы

PlantUML диаграммы архитектуры в [diagrams/](diagrams/).

---

## 🔧 Для контрибьюторов

| Документ | Описание |
|----------|----------|
| [doc/ideas/](../doc/ideas/) | Планы фаз и технические отчёты |
| [tests/README.md](../tests/README.md) | Как запускать и писать тесты |

---

## 📊 Архитектура (обзор)

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI / API                           │
├─────────────────────────────────────────────────────────────┤
│                      SemanticCore                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Embedder   │  │ VectorStore │  │ LLMProvider │         │
│  │  (Gemini)   │  │  (Peewee)   │  │  (Gemini)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                   SQLite + sqlite-vec                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔗 Связанные ресурсы

- [GitHub Repository](https://github.com/VladimirMonin/poc_vector_sqlite)
- [Архитектурный сериал](../doc/architecture/00_overview.md) — детальные технические документы
- [Phase Reports](../doc/ideas/) — история разработки

---

**Версия документации**: Phase 11 | **Последнее обновление**: Декабрь 2025
