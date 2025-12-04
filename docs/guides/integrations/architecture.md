---
title: "Integration Architecture"
description: "Паттерны интеграции: Singleton, DI, Lifecycle"
tags: ["integration", "di", "singleton", "architecture"]
difficulty: "intermediate"
prerequisites: ["sync-nature"]
---

# Integration Architecture 🏗️

> Как правильно создавать и прокидывать SemanticCore в приложение.

---

## Ключевая идея 💡

Создавайте `SemanticCore` **один раз** при старте приложения.
Прокидывайте через Dependency Injection или app state.

---

## Паттерн: Singleton 📦

```
┌─────────────────────────────────────────────┐
│              Application Start               │
│                                              │
│  core = SemanticCore.from_config()          │
│                     │                        │
│        ┌───────────┴───────────┐            │
│        ▼           ▼           ▼            │
│   [Request 1] [Request 2] [Request N]       │
│        │           │           │            │
│        └───────────┴───────────┘            │
│                     │                        │
│              Один core                      │
│              Одно соединение SQLite         │
└─────────────────────────────────────────────┘
```

---

## Django 🐍

### Вариант 1: В settings.py

```python
# settings.py
from semantic_core import SemanticCore

_SEMANTIC_CORE = None

def get_semantic_core():
    global _SEMANTIC_CORE
    if _SEMANTIC_CORE is None:
        _SEMANTIC_CORE = SemanticCore.from_config()
    return _SEMANTIC_CORE
```

```python
# views.py
from django.conf import settings

def search_view(request):
    core = settings.get_semantic_core()
    results = core.search(request.GET['q'])
    return JsonResponse(...)
```

### Вариант 2: AppConfig.ready()

```python
# apps.py
from django.apps import AppConfig

class SearchConfig(AppConfig):
    name = 'search'
    
    def ready(self):
        from semantic_core import SemanticCore
        self.core = SemanticCore.from_config()
```

---

## FastAPI ⚡

### Рекомендуемый: Lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from semantic_core import SemanticCore

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.core = SemanticCore.from_config()
    yield
    # Shutdown (cleanup если нужно)

app = FastAPI(lifespan=lifespan)

@app.get("/search")
async def search(request: Request, q: str):
    core = request.app.state.core
    # ... используем core
```

### Dependency Injection

```python
from fastapi import Depends

def get_core(request: Request) -> SemanticCore:
    return request.app.state.core

@app.get("/search")
async def search(q: str, core: SemanticCore = Depends(get_core)):
    results = await run_in_threadpool(core.search, q)
    return {"results": ...}
```

---

## Flask 🍼

```python
from flask import Flask, g
from semantic_core import SemanticCore

app = Flask(__name__)

# Инициализация при старте
with app.app_context():
    app.semantic_core = SemanticCore.from_config()

@app.route('/search')
def search():
    results = app.semantic_core.search(request.args['q'])
    return jsonify(results=...)
```

---

## SQLite: Один файл, много потоков 💾

SemanticCore использует **свой SQLite файл** (semantic.db).

```
┌─────────────────────────────────────────────┐
│           Ваше приложение                   │
│                                              │
│  ┌──────────────┐  ┌──────────────┐         │
│  │ App Database │  │ semantic.db  │         │
│  │  (Postgres)  │  │  (SQLite)    │         │
│  └──────────────┘  └──────────────┘         │
│         │                  │                 │
│    Django ORM      SemanticCore             │
│                                              │
│  ⚠️ НЕ пересекаются!                        │
└─────────────────────────────────────────────┘
```

**Важно**: SQLite с WAL mode thread-safe для чтения.
Записи сериализуются автоматически.

---

## Lifecycle: Когда создавать? 🔄

| Момент | Действие |
|--------|----------|
| App start | `SemanticCore.from_config()` |
| Request | Получить из app.state / DI |
| App shutdown | Ничего (SQLite закроется автоматически) |

**Не создавайте** core в каждом запросе — это медленно и течёт память.

---

## Частые ошибки ⚠️

| Ошибка | Почему | Решение |
|--------|--------|---------|
| Core в каждом запросе | Медленная инициализация | Singleton паттерн |
| Глобальная переменная без lazy init | Может сломать импорты | Используйте `get_*()` функцию |
| Закрытие соединения в shutdown | Не нужно для SQLite | Уберите cleanup |

---

## Следующие шаги 🔗

| Гайд | Что узнаете |
|------|-------------|
| [Peewee Integration](peewee.md) | Нативная ORM интеграция |
| [Custom ORM](custom-orm.md) | Как написать свой адаптер |
