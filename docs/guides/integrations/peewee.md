---
title: "Peewee Integration"
description: "Нативная интеграция с Peewee ORM через SemanticIndex"
tags: ["integration", "peewee", "orm", "native"]
difficulty: "intermediate"
prerequisites: ["architecture"]
---

# Peewee Integration 🐍

> Нативная интеграция: `Article.search.hybrid("query")` прямо из ORM.

---

## Ключевая идея 💡

`SemanticIndex` — дескриптор, который добавляет семантический поиск
к любой Peewee модели. Автоиндексация при save/delete.

---

## Быстрый старт 🚀

```python
from peewee import Model, CharField, TextField
from semantic_core import SemanticCore, SemanticIndex

core = SemanticCore.from_config()

class Article(Model):
    title = CharField()
    content = TextField()
    
    # Добавляем семантический поиск
    search = SemanticIndex(
        core=core,
        content_field="content",
        context_fields=["title"],
    )
```

---

## Два режима доступа 📐

```
┌─────────────────────────────────────────────┐
│           SemanticIndex Descriptor           │
├──────────────────────┬──────────────────────┤
│   Class Access       │   Instance Access    │
│   Article.search     │   article.search     │
│         │            │         │            │
│         ▼            │         ▼            │
│   SearchProxy        │   InstanceManager    │
│   .hybrid()          │   .update()          │
│   .vector()          │   .delete()          │
│   .fts()             │                      │
└──────────────────────┴──────────────────────┘
```

---

## Поиск через класс 🔍

```python
# Гибридный поиск (RRF)
results = Article.search.hybrid("machine learning", limit=10)

# Только векторный
results = Article.search.vector("neural networks")

# Только FTS
results = Article.search.fts("python")

# Результат — ORM объекты!
for article in results:
    print(article.title)  # ✅ Полный ORM объект
```

---

## Управление через инстанс 📝

```python
article = Article.get_by_id(42)

# Принудительно переиндексировать
article.search.update()

# Удалить из индекса (без удаления из БД)
article.search.delete()
```

---

## Автоиндексация ⚡

SemanticIndex патчит `save()` и `delete_instance()`:

```
┌─────────────────────────────────────────────┐
│           article.save()                     │
│                 │                            │
│                 ▼                            │
│  ┌─────────────────────────────┐            │
│  │  PeeweeAdapter._patch_save  │            │
│  │                             │            │
│  │  1. original_save()         │            │
│  │  2. SemanticIndex._handle_save()         │
│  │     → builder.build(article)             │
│  │     → core.ingest(doc)                   │
│  └─────────────────────────────┘            │
└─────────────────────────────────────────────┘
```

**Автоматически**:
- ✅ При `save()` — индексирует (create) или обновляет (update)
- ✅ При `delete_instance()` — удаляет из индекса

---

## Параметры SemanticIndex 📋

| Параметр | Описание |
|----------|----------|
| `core` | Экземпляр SemanticCore |
| `content_field` | Поле с основным текстом |
| `context_fields` | Поля для метаданных (title, author) |
| `filter_fields` | Поля для фильтрации |
| `media_fields` | Поля с путями к медиа |

```python
search = SemanticIndex(
    core=core,
    content_field="body",
    context_fields=["title", "author"],
    filter_fields=["category", "status"],
)
```

---

## Множественные индексы 📚

Одна модель может иметь несколько индексов:

```python
class Document(Model):
    title = CharField()
    content = TextField()
    summary = TextField()
    
    # Поиск по полному тексту
    full_search = SemanticIndex(
        core=core,
        content_field="content",
    )
    
    # Поиск только по summary
    quick_search = SemanticIndex(
        core=core,
        content_field="summary",
    )
```

```python
# Разные индексы — разные результаты
Document.full_search.hybrid("query")
Document.quick_search.hybrid("query")
```

---

## init_database() 🗄️

Для веб-приложения — вызывайте при старте:

```python
from semantic_core.database import init_database

# Django: в AppConfig.ready()
# FastAPI: в lifespan
# Flask: с app_context

init_database()  # Создаёт таблицы если нет
```

---

## Частые ошибки ⚠️

| Ошибка | Почему | Решение |
|--------|--------|---------|
| `Cannot set attribute` | SemanticIndex read-only | Не присваивайте `model.search = ...` |
| Дубликаты в индексе | save() без id | Проверьте что id существует |
| Пустые результаты | Индексация не произошла | Проверьте `save()` был вызван |

---

## Следующие шаги 🔗

| Гайд | Что узнаете |
|------|-------------|
| [Custom ORM](custom-orm.md) | Адаптер для Django/SQLAlchemy |
| [Plugin System](../../concepts/10_plugin_system.md) | Архитектура интерфейсов |
