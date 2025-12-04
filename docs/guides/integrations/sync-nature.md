---
title: "Sync Nature"
description: "Semantic Core — синхронная библиотека. Как интегрировать с async."
tags: ["integration", "async", "sync", "fastapi", "event-loop"]
difficulty: "intermediate"
prerequisites: ["../core/quickstart"]
---

# Sync Nature ⚡

> Semantic Core — **синхронная библиотека**. Это важно понимать при интеграции.

---

## Ключевая идея 💡

SemanticCore блокирует поток во время выполнения.
В async-фреймворках это заблокирует Event Loop.

---

## Почему синхронная? 🔍

| Компонент | Причина |
|-----------|---------|
| SQLite | Файловая БД, блокирующий I/O |
| Gemini API | HTTP запросы (можно обернуть, но...) |
| sqlite-vec | C-расширение, синхронное |

Async-обёртка добавила бы сложность без реальной выгоды.

---

## Матрица совместимости 📊

| Фреймворк | Тип | Как использовать |
|-----------|-----|------------------|
| Django | Sync | Напрямую ✅ |
| Flask | Sync | Напрямую ✅ |
| FastAPI | Async | `run_in_threadpool()` |
| Litestar | Async | `run_sync()` |
| aiohttp | Async | `loop.run_in_executor()` |

---

## Sync фреймворки (Django, Flask) ✅

Вызывайте напрямую:

```python
# Django view
def search_view(request):
    query = request.GET.get('q')
    results = core.search(query)  # ✅ Блокирует, но это OK
    return JsonResponse({'results': [...]})
```

```python
# Flask route
@app.route('/search')
def search():
    query = request.args.get('q')
    results = core.search(query)  # ✅ OK
    return jsonify(results=[...])
```

---

## Async фреймворки (FastAPI) ⚠️

### Проблема

```python
@app.get("/search")
async def search(q: str):
    results = core.search(q)  # ❌ Блокирует Event Loop!
    return {"results": results}
```

Пока `search()` выполняется, весь сервер "замирает".

### Решение: Thread Pool

```python
from fastapi.concurrency import run_in_threadpool

@app.get("/search")
async def search(q: str):
    # ✅ Выполняется в отдельном потоке
    results = await run_in_threadpool(core.search, q)
    return {"results": results}
```

---

## Диаграмма: Thread Pool 📐

```
┌─────────────────────────────────────────────────┐
│              Event Loop (main)                  │
│                                                 │
│  request ──▶ run_in_threadpool() ──▶ response  │
│                      │                          │
│                      ▼                          │
│            ┌─────────────────┐                 │
│            │  Thread Pool    │                 │
│            │                 │                 │
│            │  core.search()  │  ◀─ Блокирует  │
│            │  SQLite + API   │     только тред│
│            │                 │                 │
│            └─────────────────┘                 │
└─────────────────────────────────────────────────┘
```

---

## Litestar

```python
from litestar.concurrency import run_sync

@get("/search")
async def search(q: str) -> dict:
    results = await run_sync(core.search, q)
    return {"results": results}
```

---

## aiohttp

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def search_handler(request):
    q = request.query.get('q')
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(executor, core.search, q)
    return web.json_response({"results": results})
```

---

## Частые ошибки ⚠️

| Ошибка | Почему | Решение |
|--------|--------|---------|
| Async endpoint без threadpool | Блокирует все запросы | Используйте `run_in_threadpool()` |
| Sync endpoint в async фреймворке | Может работать, но не масштабируется | Переделайте на async + threadpool |
| Создание Core в каждом запросе | Медленно, течёт память | Singleton / app.state |

---

## Производительность 📈

Thread Pool справляется отлично для типичных нагрузок:

| Операция | Время | Thread Pool OK? |
|----------|-------|-----------------|
| search() | 50-200ms | ✅ |
| ingest() | 100-500ms | ✅ |
| Batch ingest | 1-10s | ⚠️ Background task |

Для тяжёлых операций используйте Celery/RQ.

---

## Следующие шаги 🔗

| Гайд | Что узнаете |
|------|-------------|
| [Architecture](architecture.md) | Singleton, DI, lifecycle |
| [Peewee Integration](peewee.md) | Нативная ORM интеграция |
