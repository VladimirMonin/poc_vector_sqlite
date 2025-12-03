# Отчёт Phase 6.4: Markdown Asset Enrichment (The Missing Link)

> **Статус:** ✅ Завершена  
> **Период:** ~1 день разработки  
> **Коммитов:** 1 атомарный коммит

---

## 1. Цель фазы

Закрыть пробел в интеграции: при парсинге Markdown изображения (`![alt](path)`) детектировались как `IMAGE_REF` чанки, но **не отправлялись в Gemini Vision API**. Вектора генерировались только на основе alt-текста и пути к файлу.

**Проблема "до":**

```
Markdown: "![ER-диаграмма](images/db_schema.png)"
       ↓
Chunk: IMAGE_REF, content="images/db_schema.png"
       ↓
Vector text: "Type: Image Reference, Description: ER-диаграмма, Source: images/db_schema.png"
       ↓
Embedding: [0.12, -0.34, ...] — только на основе текста, БЕЗ анализа картинки!
```

**Решение "после":**

```
Markdown: "![ER-диаграмма](images/db_schema.png)"
       ↓
Chunk: IMAGE_REF + контекст (headers, surrounding text)
       ↓
Vision API: "Diagram showing PostgreSQL database schema with tables: users, orders, products..."
       ↓
Chunk: content = description от Vision, _enriched=True
       ↓
Vector text: "Type: Image, Description: Diagram showing PostgreSQL database schema..."
       ↓
Embedding: [0.45, 0.12, ...] — на основе РЕАЛЬНОГО описания картинки!
```

---

## 2. Ключевые решения

### 2.1 Параметризация через `enrich_media`

| Решение | Обоснование |
|---------|-------------|
| `enrich_media=False` по умолчанию | Экономия токенов, явное включение, быстрый `ingest()` |
| Только `sync`/`async` режимы | Google Batch API требует GCS bucket — избегаем |
| Только `IMAGE_REF` | `![alt](src)` — 90% кейсов. Аудио/видео в MD отложены |
| Без кеширования Vision | Контекст уникален для каждого документа |

### 2.2 Передача контекста в Vision API

Vision API получает не просто изображение, а **контекст из документа**:

| Компонент | Источник | Пример |
|-----------|----------|--------|
| `breadcrumbs` | `chunk.metadata["headers"]` | "Setup > Nginx > Configuration" |
| `surrounding_text` | Соседние TEXT чанки | "[Before]: ...install nginx...\n[After]: ...restart service..." |
| `alt_text` | Markdown синтаксис | "Nginx architecture diagram" |
| `title` | Markdown синтаксис | "Figure 1" |
| `role` | Фиксированная строка | "Illustration embedded in document" |

Это помогает Vision API понять **зачем** картинка появилась в документе и сгенерировать более релевантное описание.

### 2.3 Резолв путей к изображениям

Порядок проверок в `_resolve_image_path()`:

1. **Пропуск URL** — `http://`, `https://`, `data:` игнорируются (внешние ресурсы)
2. **Абсолютный путь** — если существует, используем
3. **Относительно документа** — `doc_dir / image_ref`
4. **Относительно CWD** — `Path.cwd() / image_ref`

Если файл не найден — логируем warning и продолжаем (graceful degradation).

---

## 3. Архитектура

### 3.1 Новый компонент: MarkdownAssetEnricher

```
semantic_core/processing/enrichers/
├── __init__.py
└── markdown_assets.py
    ├── MediaContext (dataclass)
    │   ├── breadcrumbs: str
    │   ├── surrounding_text: str
    │   ├── alt_text: str
    │   ├── title: str
    │   ├── role: str
    │   └── format_for_vision() -> str
    │
    └── MarkdownAssetEnricher
        ├── context_window: int = 200
        ├── skip_code_chunks: bool = True
        ├── get_context(chunk, all_chunks) -> MediaContext
        └── _find_neighbor_text(chunks, idx, direction) -> str
```

### 3.2 Алгоритм `get_context()`

1. Извлечь `headers` из `chunk.metadata` → breadcrumbs
2. Найти предыдущий TEXT-чанк → последние N символов
3. Найти следующий TEXT-чанк → первые N символов
4. Пропустить CODE чанки (они не дают полезного контекста)
5. Собрать `MediaContext`

### 3.3 Модификация pipeline

Новые методы в `SemanticCore`:

| Метод | Назначение |
|-------|------------|
| `_enrich_media_chunks()` | Основная логика обогащения |
| `_get_document_directory()` | Извлекает директорию документа из metadata |
| `_resolve_image_path()` | Резолвит относительные пути |
| `_analyze_image_for_chunk()` | Вызывает Vision API с rate limiting |

### 3.4 Модификация HierarchicalContextStrategy

Добавлена ветка для обогащённых IMAGE_REF чанков:

| Условие | Формат vector_text |
|---------|-------------------|
| `_enriched=True` | "Type: Image\nDescription: {vision_description}\nVisible text: {ocr}\nKeywords: {...}\nSource: {path}" |
| `_enriched=False` | "Type: Image Reference\nDescription: {alt}\nSource: {path}" |

---

## 4. Потоки данных

### 4.1 Sync режим

```
ingest(doc, enrich_media=True, mode="sync")
    │
    ├─> splitter.split(doc) → chunks[]
    │
    ├─> _enrich_media_chunks(chunks, doc, mode="sync")
    │   │
    │   └─> для каждого IMAGE_REF:
    │       ├─> _resolve_image_path() → Path | None
    │       ├─> enricher.get_context() → MediaContext
    │       ├─> _analyze_image_for_chunk() → {description, keywords, ocr}
    │       └─> chunk.content = description
    │           chunk.metadata["_enriched"] = True
    │           chunk.metadata["_original_path"] = path
    │
    ├─> context_strategy.form_vector_text() → vector_texts[]
    │
    ├─> embedder.embed_documents(vector_texts) → embeddings[]
    │
    └─> store.save(doc, chunks)
```

### 4.2 Async режим

```
ingest(doc, enrich_media=True, mode="async")
    │
    ├─> splitter.split(doc) → chunks[]
    │
    ├─> _enrich_media_chunks(chunks, doc, mode="async")
    │   │
    │   └─> для каждого IMAGE_REF:
    │       ├─> _resolve_image_path() → Path | None
    │       ├─> enricher.get_context() → MediaContext
    │       └─> _create_media_task(path, context_text)
    │           chunk.metadata["_media_task_id"] = task_id
    │           chunk.metadata["_pending_enrichment"] = True
    │
    ├─> context_strategy.form_vector_text() → vector_texts[]
    │   (для pending chunks — alt-text based)
    │
    ├─> chunks помечаются PENDING (без векторов)
    │
    └─> store.save(doc, chunks)

    ... позже ...

process_media_queue()
    └─> MediaQueueProcessor обрабатывает задачи
        └─> Обновляет чанки с результатами Vision
```

---

## 5. Обработка ошибок

Философия: **никогда не ронять весь ingest() из-за одной картинки**.

| Ситуация | Поведение |
|----------|-----------|
| Файл не найден | `logger.warning()`, `chunk.metadata["_media_error"]`, продолжаем |
| Vision API ошибка | `logger.error()`, `chunk.metadata["_media_error"]`, продолжаем |
| Внешний URL (http://) | Пропускаем, логируем debug |
| `image_analyzer` не настроен | `logger.warning()`, возвращаем чанки без обогащения |
| Невалидный формат изображения | `chunk.metadata["_media_error"]`, продолжаем |

---

## 6. Метаданные чанков после обогащения

| Ключ | Тип | Описание |
|------|-----|----------|
| `_enriched` | `bool` | Vision API успешно отработал |
| `_original_path` | `str` | Путь к файлу до замены content |
| `_vision_alt` | `str` | alt_text от Vision |
| `_vision_keywords` | `list[str]` | Ключевые слова от Vision |
| `_vision_ocr` | `str` | OCR текст (если есть) |
| `_media_error` | `str` | Сообщение об ошибке |
| `_media_task_id` | `str` | UUID задачи (async режим) |
| `_pending_enrichment` | `bool` | Ожидает обработки (async режим) |

---

## 7. Пример использования

### 7.1 Базовый сценарий

```python
from semantic_core import SemanticCore, Document
from semantic_core.infrastructure.gemini import GeminiEmbedder, GeminiImageAnalyzer

# Настройка с image_analyzer
core = SemanticCore(
    embedder=GeminiEmbedder(api_key=key),
    store=store,
    splitter=smart_splitter,
    context_strategy=hierarchical_context,
    image_analyzer=GeminiImageAnalyzer(api_key=key),  # Обязательно!
)

# Документ с изображениями
doc = Document(
    content="""
# Server Setup

## Nginx Configuration

Here's the architecture:

![Nginx architecture](images/nginx_diagram.png)

This shows how requests flow through the system.
""",
    metadata={"title": "Setup Guide", "source": "/docs/setup.md"},
)

# Индексация с обогащением
core.ingest(doc, enrich_media=True)  # <-- Явное включение!

# Поиск найдёт по описанию картинки
results = core.search("request flow diagram")
```

### 7.2 Async режим

```python
# Индексация без блокировки
core.ingest(doc, mode="async", enrich_media=True)

# Позже обработать очередь
processed = core.process_media_queue(max_tasks=10)
```

---

## 8. Отклонения от плана

| Планировалось | Реализовано | Причина |
|---------------|-------------|---------|
| Кеширование Vision по path+mtime | Нет кеширования | Контекст уникален для каждого документа |
| Batch режим (Google Batch API) | Только sync/async | Batch требует GCS bucket |
| Аудио/видео в Markdown | Только IMAGE_REF | Нет стандарта в Markdown |

---

## 9. Метрики реализации

| Метрика | Значение |
|---------|----------|
| Новых файлов | 2 (`enrichers/__init__.py`, `markdown_assets.py`) |
| Изменённых файлов | 2 (`pipeline.py`, `hierarchical_strategy.py`) |
| Строк кода (prod) | ~350 |
| Новых методов | 5 |

---

## 10. Definition of Done

- [x] `MarkdownAssetEnricher` извлекает контекст (surrounding text + headers)
- [x] `SemanticCore.ingest(enrich_media=True)` обрабатывает IMAGE_REF через Vision API
- [x] Битые ссылки НЕ роняют процесс (graceful degradation)
- [x] Результат анализа сохраняется с вектором
- [x] sync/async режимы работают
- [x] `HierarchicalContextStrategy` корректно форматирует обогащённые чанки
- [x] Docstrings в Google-стиле

---

## 11. Следующие шаги (Phase 6.5+)

1. **Batch режим для картинок** — если появится поддержка GCS или локального батчинга
2. **Аудио/видео в Markdown** — расширить парсер для HTML5 тегов `<audio>`, `<video>`
3. **Кеширование Vision** — если одинаковые картинки в разных документах
4. **Thumbnail preview** — сохранять превью для UI
