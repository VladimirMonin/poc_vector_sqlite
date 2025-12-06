---
phase: 14.2
title: "MediaService & Aggregation Layer"
created: 2025-12-06
topics: [service-layer, dto, aggregation, timeline]
commits: [a7045fd]
---

# 81. MediaService & Aggregation Layer

**Commits:** `a7045fd`

## Проблема

После Phase 14.1 медиа-файлы разбиваются на множество чанков:

```
video.mp4 →
  ├─ chunk_0: SUMMARY (role: summary)
  ├─ chunk_1: TRANSCRIPT [00:05] (role: transcript)
  ├─ chunk_2: TRANSCRIPT [01:30] (role: transcript)
  ├─ chunk_3: OCR code (role: ocr)
  └─ chunk_4: OCR text (role: ocr)
```

**Проблема для UI/CLI:**
- ❌ Нужно вручную собирать данные из разных чанков
- ❌ Дублирование логики сборки в Flask routes, CLI, notebooks
- ❌ Нет единой точки доступа к "полной информации о медиа"
- ❌ Сложно построить timeline для навигации по таймкодам

**Anti-pattern:**

```python
# Flask route (BAD)
@bp.route("/media/<doc_id>")
def view_media(doc_id):
    # 30+ строк ручной сборки
    summary = ChunkModel.select().where(..., role="summary").get()
    transcripts = ChunkModel.select().where(..., role="transcript").order_by(...)
    ocr_chunks = ChunkModel.select().where(..., role="ocr").order_by(...)
    # Склеиваем вручную...
```

## Решение: Сервисный слой агрегации

Создаём **MediaService** — единую точку для работы с медиа-данными.

### Архитектурный паттерн

```
┌─────────────────────────────────────────────────┐
│              UI Layer (Flask/CLI)               │
│  "Покажи всю информацию о video.mp4"            │
└──────────────────┬──────────────────────────────┘
                   │ ONE CALL
                   ▼
┌─────────────────────────────────────────────────┐
│           MediaService (Aggregation)            │
│  • get_media_details(doc_id) → MediaDetails     │
│  • get_timeline(doc_id) → Timeline[]            │
│  • get_chunks_by_role(doc_id, role) → Chunk[]   │
└──────────────────┬──────────────────────────────┘
                   │ DB QUERIES
                   ▼
┌─────────────────────────────────────────────────┐
│         Database (Peewee ORM Models)            │
│  ChunkModel.select().where(document=doc_id)     │
└─────────────────────────────────────────────────┘
```

**Преимущества:**
- ✅ **DRY**: Логика сборки в одном месте
- ✅ **Reusable**: Используется в Flask, CLI, notebooks, RAG
- ✅ **Testable**: Изолированные unit-тесты с моками
- ✅ **Type-safe**: Pydantic DTO с валидацией

## Компоненты решения

### 1. DTO Models (Data Transfer Objects)

**Файл:** `semantic_core/domain/media_dto.py`

Два DTO для структурированного представления:

#### TimelineItem

Элемент timeline для медиа-плеера:

| Поле              | Тип    | Описание                          |
|-------------------|--------|-----------------------------------|
| `chunk_id`        | str    | ID чанка в БД                     |
| `start_seconds`   | int    | Временная метка (секунды)         |
| `content_preview` | str    | Превью контента (100 символов)    |
| `role`            | str    | "transcript" или "ocr"            |
| `chunk_type`      | str    | "text", "code", etc.              |

**Фича:** `formatted_time` property — автоматическое форматирование:
- `65` → `"01:05"`
- `3665` → `"1:01:05"`

#### MediaDetails

Агрегированные данные о медиа-файле:

| Поле               | Тип           | Описание                           |
|--------------------|---------------|------------------------------------|
| `document_id`      | str           | ID документа                       |
| `media_path`       | Path          | Путь к медиа-файлу                 |
| `media_type`       | str           | "image", "audio", "video"          |
| `summary`          | str           | Краткое описание (summary chunk)   |
| `keywords`         | list[str]     | Ключевые слова                     |
| `full_transcript`  | str \| None   | Склеенная транскрипция             |
| `transcript_chunks`| list[Chunk]   | Исходные transcript чанки          |
| `full_ocr_text`    | str \| None   | Склеенный OCR текст                |
| `ocr_chunks`       | list[Chunk]   | Исходные OCR чанки                 |
| `timeline`         | list[TimelineItem] \| None | Timeline для навигации   |
| `duration_seconds` | int \| None   | Длительность медиа                 |
| `participants`     | list[str] \| None | Участники (для встреч)         |
| `action_items`     | list[str] \| None | Action items                   |

**Properties:**
- `has_timeline` — есть ли таймкоды
- `has_transcript` — есть ли транскрипция
- `has_ocr` — есть ли OCR данные
- `total_chunks` — общее количество чанков (summary + transcript + OCR)

### 2. MediaService — методы агрегации

**Файл:** `semantic_core/services/media_service.py`

#### get_media_details()

Главный метод — собирает всё в одно DTO:

**Алгоритм:**
1. Загружает документ из БД (проверка существования)
2. Проверяет, что это медиа-файл (media_type ∈ {image, audio, video})
3. Загружает все чанки документа
4. Группирует по `metadata.role`:
   - `role="summary"` → извлекает keywords, duration, participants
   - `role="transcript"` → собирает в список, строит timeline
   - `role="ocr"` → собирает в список, строит timeline
5. Склеивает transcript/OCR в единый текст (`\n\n` разделитель)
6. Сортирует timeline по `start_seconds`
7. Возвращает `MediaDetails`

**Фильтры:**
- `include_transcript=False` — исключить транскрипцию
- `include_ocr=False` — исключить OCR данные

**Использование:**

```python
service = MediaService()
details = service.get_media_details("doc-123")

print(details.summary)               # "Видео о Python разработке"
print(details.full_transcript[:100]) # "Привет! Сегодня поговорим о..."
print(details.total_chunks)          # 5 (1 summary + 2 transcript + 2 OCR)

if details.has_timeline:
    for item in details.timeline:
        print(f"{item.formatted_time}: {item.content_preview}")
    # 00:05: Привет! Сегодня поговорим о Python.
    # 01:30: Давайте начнем с основ.
```

#### get_timeline()

Возвращает **только чанки с таймкодами**, готовые для плеера.

**Фильтр:** `role_filter="transcript"` — показать только транскрипцию.

**Использование:**

```python
# Все чанки с таймкодами
timeline = service.get_timeline("doc-123")

# Только transcript (для аудио)
timeline = service.get_timeline("doc-123", role_filter="transcript")
```

#### get_chunks_by_role()

Фильтрация чанков по роли.

**Использование:**

```python
# Получить summary chunk
summary = service.get_chunks_by_role("doc-123", "summary")[0]

# Получить все transcript chunks
transcripts = service.get_chunks_by_role("doc-123", "transcript")
```

## Тестирование

**Файл:** `tests/unit/services/test_media_service.py`

**9 unit-тестов** с моками Peewee ORM:

| Тест                                      | Проверка                              |
|-------------------------------------------|---------------------------------------|
| `test_get_media_details_success`          | Успешная агрегация всех компонентов   |
| `test_get_media_details_document_not_found` | Обработка отсутствующего документа   |
| `test_get_media_details_not_media_file`   | Проверка типа документа               |
| `test_get_media_details_no_summary_chunk` | Валидация обязательного summary       |
| `test_get_media_details_include_filters`  | Фильтры include_transcript/include_ocr|
| `test_get_timeline_success`               | Построение timeline                   |
| `test_get_timeline_with_role_filter`      | Фильтрация timeline по роли           |
| `test_get_chunks_by_role`                 | Фильтрация чанков                     |
| `test_timeline_item_formatted_time`       | Форматирование времени                |

**Паттерн тестирования:** Fixture-based mocking (не `@patch` декораторы).

**Все тесты:** 9/9 PASSED ✅

## Технические детали

### Обработка исключений

Используется **`peewee.DoesNotExist`** (базовое исключение Peewee), а не `DocumentModel.DoesNotExist`.

**Почему:** `peewee.DoesNotExist` — это Exception, а `DocumentModel.DoesNotExist` — динамический атрибут класса (не Exception в момент импорта).

```python
from peewee import DoesNotExist  # ✅ Правильно

try:
    doc = DocumentModel.get_by_id(doc_id)
except DoesNotExist:  # Работает всегда
    raise ValueError(f"Document {doc_id} not found")
```

### Конвертация ORM → Domain

Метод `_chunk_model_to_domain()` конвертирует Peewee модель в domain Chunk:

**Оптимизация:** `embedding=None` — не загружаем векторы (экономия памяти).

**Зачем:** Domain объекты изолированы от ORM, можно использовать вне БД (тесты, сериализация).

### Timeline сортировка

Timeline автоматически сортируется по `start_seconds` ASC:

```python
timeline = sorted(timeline_items, key=lambda x: x.start_seconds)
```

Это гарантирует корректный порядок даже если чанки в БД не упорядочены.

## Интеграция с UI

### Flask использование

```python
from semantic_core.services import MediaService

@bp.route("/media/<doc_id>")
def view_media(doc_id):
    service = MediaService()
    details = service.get_media_details(doc_id)
    
    return render_template("media.html",
        summary=details.summary,
        transcript=details.full_transcript,
        timeline=details.timeline,
        has_timeline=details.has_timeline,
    )
```

**Результат:** 30+ строк кода → 4 строки.

### CLI использование

```python
from semantic_core.services import MediaService

def show_media_info(doc_id: str):
    service = MediaService()
    details = service.get_media_details(doc_id)
    
    console.print(f"[bold]{details.summary}[/bold]")
    console.print(f"Keywords: {', '.join(details.keywords)}")
    
    if details.has_timeline:
        for item in details.timeline:
            console.print(f"  {item.formatted_time}: {item.content_preview}")
```

## Статистика Phase 14.2

| Метрика          | Значение                  |
|------------------|---------------------------|
| **Новые классы** | 2 (MediaDetails, TimelineItem) |
| **Методы**       | 3 (get_media_details, get_timeline, get_chunks_by_role) |
| **Unit-тесты**   | 9 (100% passing)          |
| **Commit**       | `a7045fd`                 |
| **Общий счёт**   | 1024 теста в проекте      |

## Архитектурные уроки

### 1. Сервисный слой — DRY принцип

**До:** Логика сборки дублируется в Flask, CLI, notebooks.  
**После:** Один MediaService для всех клиентов.

### 2. DTO изоляция

**DTO (Data Transfer Objects)** отделяют domain от представления:
- Domain: `Chunk`, `Document` (business logic)
- DTO: `MediaDetails`, `TimelineItem` (presentation logic)

### 3. Properties для читаемости

```python
if details.has_timeline:  # ✅ Читаемо
    # vs
if details.timeline and len(details.timeline) > 0:  # ❌ Многословно
```

### 4. Автоматическая сортировка

Timeline **всегда** отсортирован — нет риска показать пользователю хаос.

## Следующие шаги

**Phase 14.3 (если понадобится):**
- Расширение Search API для фильтрации по `chunk.metadata.role`
- Кэширование MediaDetails в Redis
- Batch-агрегация для множества документов

**Текущий статус:** Phase 14.2 COMPLETED ✅
