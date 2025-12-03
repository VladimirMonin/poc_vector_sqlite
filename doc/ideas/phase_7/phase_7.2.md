# 📋 Phase 7.2: Infrastructure Layer Instrumentation

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 7.0 (Logging Core) ✅

> **Примечание:** Phase 7.2 НЕ зависит от Phase 7.1. Можно выполнять параллельно!

---

## ✅ ПРЕДВАРИТЕЛЬНО ВЫПОЛНЕНО

> **ВАЖНО для агента:** Следующие задачи УЖЕ ВЫПОЛНЕНЫ. НЕ нужно их делать повторно!

1. ✅ **EMOJI_MAP обновлён** — все паттерны для Phase 7.2 добавлены в `formatters.py`:
   - `batch`, `batching`, `queue` → 📦
   - `api` → 🌐
   - `rate`, `limit`, `limiter`, `resilience` → 🛡️
   - `retry` → 🔄
   - `engine`, `model`, `models` → 🗄️
   - `file`, `files` → 📁
   - `token`, `tokens` → 🔢
   - `frame`, `frames` → 🎞️
   - `optimize`, `optimization` → ⚡
   
2. ✅ **Logging Core готов** — `get_logger()`, `bind()`, `trace()` работают

**Агент НЕ должен трогать файл `semantic_core/utils/logger/formatters.py`!**

---

## 🎯 Цель

Внедрить семантическое логирование в инфраструктурный слой: API-вызовы Gemini, хранилище данных, обработку медиа. Получить **полную видимость** внешних операций: latency, ошибки, retry.

---

## 📦 Целевые модули

### Gemini API (7 файлов)

```
semantic_core/infrastructure/gemini/
├── embedder.py          # GeminiEmbedder
├── image_analyzer.py    # GeminiImageAnalyzer
├── audio_analyzer.py    # GeminiAudioAnalyzer
├── video_analyzer.py    # GeminiVideoAnalyzer
├── batching.py          # BatchAPIClient
├── rate_limiter.py      # TokenBucketRateLimiter
└── resilience.py        # retry_with_backoff, error classification
```

### Storage (3 файла)

```
semantic_core/infrastructure/storage/peewee/
├── adapter.py           # PeeweeVectorStore / PeeweeAdapter
├── engine.py            # Database engine setup
└── models.py            # ORM models (ChunkModel, MediaTaskModel)
```

### Media Utils (5 файлов)

```
semantic_core/infrastructure/media/utils/
├── images.py            # Pillow: resize, optimize
├── audio.py             # pydub: extract, compress
├── video.py             # imageio: frame extraction
├── tokens.py            # Token estimation
└── files.py             # Path resolution, MIME detection
```

### Core (1 файл)

```
semantic_core/core/
└── media_queue.py       # MediaQueueProcessor
```

**Всего: 16 файлов**

---

## 🔍 Детальный план по группам

---

### Группа 1: Gemini API

#### 1.1 `embedder.py` — GeminiEmbedder

**Эмодзи модуля:** 🧠 (паттерн `embed`, `gemini`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `embed_documents()` вход | DEBUG | Количество документов, модель |
| `embed_documents()` выход | INFO | Успех, latency_ms, tokens_used |
| `embed_query()` | DEBUG | Длина запроса |
| API call | TRACE | Request payload (без контента!) |
| Rate limit wait | WARNING | Время ожидания |
| Retry | WARNING | Номер попытки, причина |

**Метрики в логах:**
- `latency_ms` — время API-вызова
- `tokens_used` — использованные токены
- `batch_size` — размер батча

---

#### 1.2 `image_analyzer.py` — GeminiImageAnalyzer

**Эмодзи модуля:** 👁️ (паттерн `image`, `vision`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `analyze()` вход | DEBUG | Путь к файлу, размер, prompt длина |
| `analyze()` выход | INFO | Успех, latency_ms, response_length |
| `_prepare_image()` | TRACE | Оригинальный размер → оптимизированный |
| `_estimate_tokens()` | TRACE | Расчёт токенов изображения |
| API error | ERROR | Код ошибки, retryable? |

---

#### 1.3 `audio_analyzer.py` — GeminiAudioAnalyzer

**Эмодзи модуля:** 🎙️ (паттерн `audio`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `analyze()` вход | DEBUG | Путь, duration_sec, format |
| `analyze()` выход | INFO | Успех, latency_ms, transcript_length |
| `_optimize_audio()` | DEBUG | Bitrate оригинал → оптимизированный |
| Chunking decision | TRACE | Нужно ли разбивать на части |

---

#### 1.4 `video_analyzer.py` — GeminiVideoAnalyzer

**Эмодзи модуля:** 🎬 (паттерн `video`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `analyze()` вход | DEBUG | Путь, duration, frame_mode |
| `analyze()` выход | INFO | Успех, frames_extracted, latency_ms |
| `_extract_frames()` | DEBUG | Количество кадров, интервал |
| `_extract_audio()` | DEBUG | Аудио дорожка: есть/нет, duration |
| Combined request | TRACE | Размер multimodal payload |

---

#### 1.5 `batching.py` — BatchAPIClient

**Эмодзи модуля:** 📦 (паттерн `batch`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `submit_batch()` | INFO | batch_id, item_count |
| `check_status()` | DEBUG | batch_id, current_status |
| `retrieve_results()` | INFO | batch_id, success_count, failed_count |
| Status transition | DEBUG | PENDING → PROCESSING → COMPLETED |
| Batch error | ERROR | batch_id, error_message |

---

#### 1.6 `rate_limiter.py` — TokenBucketRateLimiter

**Эмодзи модуля:** 🛡️ (паттерн `rate`, `limit`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `acquire()` | TRACE | tokens_requested, tokens_available |
| `acquire()` wait | DEBUG | wait_time_ms |
| Bucket refill | TRACE | tokens_added, new_level |
| Throttle triggered | WARNING | Запрос задержан на X ms |

---

#### 1.7 `resilience.py` — Retry & Error Classification

**Эмодзи модуля:** 🛡️ (паттерн `resilience`)

| Функция | Уровень | Что логируем |
|---------|---------|--------------|
| `is_retryable()` | TRACE | error_type, decision |
| `@retry_with_backoff` attempt | DEBUG | attempt_number, delay_ms |
| `@retry_with_backoff` success | INFO | Успех после N попыток |
| `@retry_with_backoff` exhausted | ERROR | Все попытки исчерпаны |

---

### Группа 2: Storage Layer

#### 2.1 `adapter.py` — PeeweeVectorStore / PeeweeAdapter

**Эмодзи модуля:** 💾 (паттерн `storage`, `adapter`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `store_chunks()` | INFO | chunk_count, doc_id |
| `store_chunks()` detail | DEBUG | Каждый chunk: id, type, token_count |
| `search_vector()` | DEBUG | query_length, limit, filters |
| `search_vector()` result | INFO | results_count, latency_ms |
| `search_hybrid()` | DEBUG | Параметры RRF |
| `delete_by_doc()` | INFO | doc_id, deleted_count |
| SQL execution | TRACE | Query (без данных), execution_time |

---

#### 2.2 `engine.py` — Database Engine

**Эмодзи модуля:** 💾 (паттерн `engine`, `database`)

| Функция | Уровень | Что логируем |
|---------|---------|--------------|
| `create_engine()` | INFO | db_path, extensions_loaded |
| `load_extensions()` | DEBUG | vec0, fts5 статус |
| Connection error | ERROR | Причина, путь к БД |

---

#### 2.3 `models.py` — ORM Models

**Эмодзи модуля:** 💾 (паттерн `model`)

| Событие | Уровень | Что логируем |
|---------|---------|--------------|
| Table creation | DEBUG | table_name, columns |
| Migration | INFO | Added column X to table Y |

**Примечание:** Модели обычно не содержат бизнес-логики. Логирование минимальное.

---

### Группа 3: Media Utils

#### 3.1 `images.py` — Image Processing

**Эмодзи модуля:** 👁️ (паттерн `image`)

| Функция | Уровень | Что логируем |
|---------|---------|--------------|
| `resize_image()` | DEBUG | original_size → target_size |
| `optimize_for_api()` | DEBUG | format, quality, result_bytes |
| `calculate_tokens()` | TRACE | dimensions → token_estimate |
| Error | ERROR | Pillow exception, file_path |

---

#### 3.2 `audio.py` — Audio Processing

**Эмодзи модуля:** 🎙️ (паттерн `audio`)

| Функция | Уровень | Что логируем |
|---------|---------|--------------|
| `extract_audio()` | DEBUG | source_path, output_format |
| `compress_audio()` | DEBUG | original_bitrate → target_bitrate |
| `get_duration()` | TRACE | duration_seconds |
| FFmpeg command | TRACE | Команда (без путей) |
| Error | ERROR | pydub/FFmpeg exception |

---

#### 3.3 `video.py` — Video Processing

**Эмодзи модуля:** 🎬 (паттерн `video`)

| Функция | Уровень | Что логируем |
|---------|---------|--------------|
| `extract_frames()` | DEBUG | video_path, frame_count, mode |
| `get_video_info()` | TRACE | duration, fps, resolution |
| Frame extraction | TRACE | frame_index, timestamp |
| Error | ERROR | imageio/pyav exception |

---

#### 3.4 `tokens.py` — Token Estimation

**Эмодзи модуля:** 🔢 (добавить паттерн `token`)

| Функция | Уровень | Что логируем |
|---------|---------|--------------|
| `estimate_text_tokens()` | TRACE | text_length → token_count |
| `estimate_image_tokens()` | TRACE | dimensions → token_count |
| `estimate_audio_tokens()` | TRACE | duration → token_count |

---

#### 3.5 `files.py` — File Utilities

**Эмодзи модуля:** 📁 (добавить паттерн `file`)

| Функция | Уровень | Что логируем |
|---------|---------|--------------|
| `resolve_path()` | TRACE | relative → absolute |
| `detect_mime()` | TRACE | path → mime_type |
| `get_file_size()` | TRACE | path → size_bytes |
| File not found | WARNING | Путь к несуществующему файлу |

---

### Группа 4: Core

#### 4.1 `media_queue.py` — MediaQueueProcessor

**Эмодзи модуля:** 📦 (паттерн `queue`)

| Метод | Уровень | Что логируем |
|-------|---------|--------------|
| `process_queue()` | INFO | Начало обработки, pending_count |
| `process_task()` | DEBUG | task_id, media_type, path |
| `process_task()` success | INFO | task_id, latency_ms |
| `process_task()` failure | ERROR | task_id, error, retry_count |
| Queue empty | DEBUG | Очередь пуста, sleeping |
| Batch complete | INFO | processed_count, failed_count |

---

## ⚙️ Обновление EMOJI_MAP

Добавить в `formatters.py`:

| Паттерн | Эмодзи | Семантика |
|---------|--------|-----------|
| `token` | 🔢 | Token counting |
| `file` | 📁 | File operations |

---

## 📐 Специальные паттерны для Infrastructure

### Паттерн: Логирование с метриками

```python
import time

def api_call(...):
    start = time.perf_counter()
    log.debug("API call starting", endpoint=endpoint)
    
    try:
        result = ...
        latency_ms = (time.perf_counter() - start) * 1000
        log.info("API call complete", latency_ms=round(latency_ms, 2))
        return result
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        log.error_with_context(e, latency_ms=round(latency_ms, 2))
        raise
```

### Паттерн: Логирование retry

```python
def retry_with_backoff(...):
    for attempt in range(max_retries):
        try:
            return func()
        except RetryableError as e:
            log.warning("Retry", attempt=attempt+1, max=max_retries, 
                       error=str(e), delay_ms=delay*1000)
            time.sleep(delay)
    log.error("All retries exhausted", attempts=max_retries)
```

### Паттерн: Не логировать контент!

```python
# ❌ ПЛОХО — утечка данных пользователя
log.debug("Processing text", content=user_text)

# ✅ ХОРОШО — только метаданные  
log.debug("Processing text", length=len(user_text), 
          hash=hashlib.md5(user_text.encode()).hexdigest()[:8])
```

---

## ✅ Acceptance Criteria

### Функциональные

1. [ ] Все 16 модулей инструментированы
2. [ ] API-вызовы логируют latency_ms
3. [ ] Retry/backoff логируют номер попытки
4. [ ] Storage операции логируют количество записей
5. [ ] Media utils логируют размеры файлов и результаты оптимизации

### Качество

6. [ ] Контент пользователя НЕ логируется (только length/hash)
7. [ ] API-ключи не попадают в логи (проверить SensitiveFilter)
8. [ ] Метрики (latency_ms, tokens) добавлены к ключевым операциям

### Тесты

9. [ ] Существующие тесты проходят
10. [ ] E2E тесты с реальными API показывают ожидаемые логи

---

## 🔧 Инструкции для агента-исполнителя

### КРИТИЧЕСКИ ВАЖНО: Полная обработка файлов

**Агент ОБЯЗАН для КАЖДОГО из 16 файлов:**

1. **Прочитать файл ЦЕЛИКОМ** через `read_file` без offset/limit
2. **Составить список ВСЕХ функций/методов** перед началом работы
3. **Найти ВСЕ точки API-вызовов** — внешние HTTP запросы
4. **Найти ВСЕ точки файловых операций** — open, read, write
5. **Использовать терминал для проверки:**
   ```bash
   # Найти все исключения
   grep -n "raise\|except\|Exception" semantic_core/infrastructure/**/*.py
   
   # Найти все return
   grep -n "return" semantic_core/infrastructure/gemini/*.py
   
   # Найти API вызовы
   grep -n "generate_content\|embed_content\|request" semantic_core/infrastructure/gemini/*.py
   ```

6. **После инструментирования каждого файла:**
   - Перечитать файл целиком
   - Убедиться что каждый метод/функция имеет логирование
   - Проверить что нет дублирования логов

### Порядок работы

**День 1: Gemini API (7 файлов)**
1. `rate_limiter.py` — простой, начинаем с него
2. `resilience.py` — добавляем логи к retry
3. `embedder.py` — основной embedder
4. `image_analyzer.py`
5. `audio_analyzer.py`
6. `video_analyzer.py`
7. `batching.py`

**День 2: Storage (3 файла)**
8. `engine.py`
9. `models.py`
10. `adapter.py`

**День 3: Media Utils + Core (6 файлов)**
11. `files.py`
12. `tokens.py`
13. `images.py`
14. `audio.py`
15. `video.py`
16. `media_queue.py`

### Чеклист для каждого файла

- [ ] Добавлен импорт логгера
- [ ] Создан `logger = get_logger(__name__)`
- [ ] Все публичные методы имеют DEBUG/INFO логи
- [ ] Все API-вызовы логируют latency_ms
- [ ] Все retry логируют attempt number
- [ ] Все except блоки логируют ошибку
- [ ] Контент пользователя не логируется
- [ ] Файл перечитан после изменений

---

## 📊 Ожидаемый результат

После Phase 7.2 при API-вызове будет видно:

```
🧠 [batch-001] Эмбеддинг 50 документов, model=text-embedding-004
🛡️ [batch-001] Rate limit: ожидание 150ms
🧠 [batch-001] Эмбеддинг завершён: latency_ms=1250, tokens=12500
💾 [batch-001] Сохранение 50 чанков
💾 [batch-001] Сохранение завершено: inserted=50, latency_ms=45
```

При обработке медиа:

```
📦 [task-42] Обработка изображения: /path/to/img.jpg
👁️ [task-42] Оптимизация: 2400x1600 → 1024x683, 2.1MB → 180KB
👁️ [task-42] Vision API: latency_ms=890, response_tokens=245
📦 [task-42] Задача завершена: total_ms=1200
```

---

## 🔗 Связанные документы

- **Предыдущая:** [Phase 7.1 — Processing Layer](phase_7.1.md)
- **Следующая:** [Phase 7.3 — Configuration & UX](phase_7.3.md)
- **Архитектура:** [Semantic Logging](../../architecture/35_semantic_logging.md)
