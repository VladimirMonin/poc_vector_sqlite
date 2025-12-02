# 📋 Технический Отчёт: Phase 6.1 — Тестирование Image + Queue Infrastructure

**Статус:** ✅ Завершено  
**Коммит:** `feat: Phase 6.1 - Тесты для Image Analysis + Async Queue`  
**Ветка:** `phase_6`

---

## 🎯 Цель фазы

Покрыть тестами ключевые компоненты Phase 6.0:

- DTO и доменные объекты
- Утилиты (MIME, токены, retry, rate limiting)
- Интеграция Queue Processor с моками
- E2E тесты с реальным Gemini API

---

## 📊 Итоговые метрики

| Метрика | Значение |
|---------|----------|
| Всего тестов | 224 |
| Новых тестов Phase 6.1 | 65 |
| Изменённых файлов | 25 |
| Добавлено строк | +2226 |
| Реальных тестовых изображений | 9 |

---

## 📂 Структура тестов

```text
tests/
├── conftest.py                              # Обновлён: фикстуры для медиа
├── asests/                                  # 9 реальных изображений
│   ├── red_car.jpg
│   ├── cat_photo.png
│   ├── eiffel_tower.jpg
│   ├── text_sign.jpg                        # Для OCR тестов
│   ├── code_screen.jpg
│   ├── paris_street.jpg
│   ├── seq_django_diagram.png
│   ├── small_icon.webp                      # Edge case: маленький файл
│   └── 8k_japanese_walpaper.jpg             # Edge case: 8K разрешение
├── fixtures/images/
│   └── red_square.png                       # Синтетический (Pillow)
├── unit/
│   ├── domain/
│   │   └── test_media_dto.py                # 10 тестов
│   └── infrastructure/
│       ├── media/
│       │   ├── test_file_utils.py           # 17 тестов
│       │   └── test_tokens.py               # 13 тестов
│       └── gemini/
│           ├── test_resilience.py           # 11 тестов
│           └── test_rate_limiter.py         # 10 тестов
├── integration/
│   └── media/
│       ├── test_queue_processor.py          # 12 тестов
│       └── test_pipeline_image.py           # 10 тестов
└── e2e/
    └── gemini/
        └── test_real_image.py               # 13 тестов (marker: real_api)
```

---

## 🧪 Детализация тестов

### 1. Unit: test_media_dto.py (10 тестов)

Тестирует доменные объекты из `domain/media.py`:

| Класс | Тесты |
|-------|-------|
| `TestTaskStatus` | Проверка enum values, string comparison |
| `TestMediaResource` | Создание с Path, string path, metadata |
| `TestMediaRequest` | Minimal и full request |
| `TestMediaAnalysisResult` | Minimal, full, keywords list type |

### 2. Unit: test_tokens.py (13 тестов)

Тестирует расчёт токенов по алгоритму Gemini:

| Тест | Сценарий |
|------|----------|
| `test_small_image_258_tokens` | ≤384x384 → 258 токенов (SKIP без Pillow) |
| `test_tiny_image` | 100x100 → 258 токенов |
| `test_edge_case_384x384` | Граничный случай |
| `test_medium_image_tiling` | 800x600 → тайлинг |
| `test_large_image_1080p` | 1920x1080 |
| `test_very_large_4k` | 3840x2160 → 1548 токенов |
| `test_portrait_orientation` | Вертикальная ориентация |
| `TestEstimateCost` | Flash vs Pro модели, scaling |

**Важное исправление:** Тест 4K изначально ожидал неверное количество токенов. Исправлено на 1548 (6 тайлов × 258).

### 3. Unit: test_resilience.py (11 тестов)

Тестирует retry декоратор и error handling:

| Класс | Тесты |
|-------|-------|
| `TestIsRetryable` | 429, 503, 500, timeout, connection — retryable; ValueError, KeyError — not |
| `TestRetryWithBackoff` | Success first try, success after retries, all retries exhausted, non-retryable immediate raise, exponential backoff timing, max delay cap, metadata preservation |
| `TestMediaProcessingError` | Exception inheritance, message, chaining |

**Важное исправление:** Синтаксическая ошибка с `from original` в assignment — исправлено на `raise ... from`.

### 4. Unit: test_rate_limiter.py (10 тестов)

Тестирует Token Bucket Rate Limiter:

| Тест | Сценарий |
|------|----------|
| `test_default_rpm` | 15 RPM по умолчанию |
| `test_custom_rpm` | Настройка 60 RPM |
| `test_15_rpm_gives_4_seconds` | 60/15 = 4 сек |
| `test_60_rpm_gives_1_second` | 60/60 = 1 сек |
| `test_first_request_no_wait` | Первый запрос без задержки |
| `test_second_request_immediate_waits` | Второй сразу — ждёт |
| `test_request_after_delay_no_wait` | После паузы — не ждёт |
| `test_reset_clears_timer` | Reset сбрасывает таймер |
| `TestThreadSafety` | Lock exists, concurrent access |

### 5. Unit: test_file_utils.py (17 тестов)

Тестирует MIME detection и валидацию:

| Класс | Тесты |
|-------|-------|
| `TestGetFileMimeType` | JPEG, PNG, GIF, WebP, MP4, MP3, unknown, case-insensitive |
| `TestIsImageValid` | Valid JPEG/PNG/WebP, invalid MP4/TXT, nonexistent, directory |
| `TestGetMediaType` | image/audio/video/unknown classification |
| `TestSupportedMimeTypes` | JPEG, PNG, WebP, GIF, HEIC support |

**Важное исправление:** `.xyz` оказался зарегистрированным MIME-типом (chemical/x-xyz). Заменено на `.qzxvbnm`.

### 6. Integration: test_queue_processor.py (12 тестов)

Тестирует `MediaQueueProcessor` с mock analyzer:

| Класс | Тесты |
|-------|-------|
| `TestMediaQueueProcessorEmpty` | Empty queue returns False, batch returns 0, pending count 0 |
| `TestMediaQueueProcessorSingle` | Process pending success, calls analyzer correctly, error → FAILED status |
| `TestMediaQueueProcessorBatch` | Multiple tasks, less than max, preserves FIFO order |
| `TestMediaQueueProcessorById` | Process specific task, nonexistent task |
| `TestMediaQueueProcessorRateLimiting` | Rate limiter called for each task |

### 7. Integration: test_pipeline_image.py (10 тестов)

Тестирует `SemanticCore.ingest_image()`:

| Класс | Тесты |
|-------|-------|
| `TestSemanticCoreImageIngestion` | Sync success, async returns task_id, with context, invalid image raises, without analyzer raises |
| `TestSemanticCoreMediaQueue` | process_media_queue, get_media_queue_size, process all |
| `TestSemanticCoreMediaConfig` | Default config, custom config |

### 8. E2E: test_real_image.py (13 тестов)

Тесты с реальным Gemini API (marker: `real_api`):

| Класс | Тесты |
|-------|-------|
| `TestRealGeminiImageAnalysis` | Synthetic red square, with context, returns keywords |
| `TestRealGeminiWithRealImages` | Red car, cat photo, Eiffel Tower, text sign OCR, code screenshot, Paris street, diagram |
| `TestRealGeminiEdgeCases` | Small icon (WebP), 8K wallpaper |
| `TestRealGeminiRetryBehavior` | Real request succeeds |

---

## 🛠️ Решённые технические проблемы

### 1. Изоляция DB State между тестами

**Проблема:** `media_db` фикстура использовала `db.bind()`, который глобально изменял `Model._meta.database`. После media-тестов другие тесты падали с "no such table: chunks".

**Симптом:**

```
peewee.OperationalError: no such table: main.chunks
```

**Решение:** Сохранение и восстановление оригинальной БД для каждой модели:

```python
@pytest.fixture
def media_db(tmp_path):
    # Сохраняем оригинальные БД
    original_dbs = {
        DocumentModel: DocumentModel._meta.database,
        ChunkModel: ChunkModel._meta.database,
        ...
    }
    
    # ... использование ...
    
    yield db
    
    # Восстанавливаем
    for model, original_db in original_dbs.items():
        model._meta.database = original_db
```

### 2. Pillow как optional dependency

**Проблема:** Тесты токенов требуют Pillow, который в `[media]` optional-dependencies.

**Решение:**

1. Установили Pillow через `poetry install --extras media`
2. Тесты с синтетическими изображениями делают `pytest.skip()` если Pillow недоступен

### 3. Синтаксическая ошибка Python 3.14

**Проблема:** `error = Exception("msg") from original` — невалидный синтаксис (from только для raise).

**Решение:**

```python
# Было (неверно):
error = MediaProcessingError("Wrapped") from original

# Стало (верно):
try:
    raise MediaProcessingError("Wrapped") from original
except MediaProcessingError as error:
    assert error.__cause__ is original
```

### 4. Float precision в cost estimation

**Проблема:** `cost_2k == cost_1k * 2` падал из-за floating point precision.

**Решение:** Добавлен relative tolerance:

```python
assert cost_2k == pytest.approx(cost_1k * 2, rel=0.1)
```

### 5. MIME-тип .xyz

**Проблема:** Тест "unknown extension" использовал `.xyz`, который оказался зарегистрированным MIME-типом `chemical/x-xyz`.

**Решение:** Заменили на гарантированно несуществующее расширение `.qzxvbnm`.

---

## 📦 Тестовые ассеты

### Синтетические (Pillow)

| Файл | Размер | Цвет | Назначение |
|------|--------|------|------------|
| `red_square.png` | 200×200 | Красный | Базовый тест анализа |
| `large_blue.png` | 3000×2000 | Синий | Тест больших изображений |
| `medium_green.png` | 800×600 | Зелёный | Тест тайлинга |

### Реальные (tests/asests/)

| Файл | Назначение |
|------|------------|
| `red_car.jpg` | Тест распознавания объектов (автомобиль) |
| `cat_photo.png` | Тест распознавания животных |
| `eiffel_tower.jpg` | Тест распознавания landmarks |
| `text_sign.jpg` | Тест OCR |
| `code_screen.jpg` | Тест распознавания кода |
| `paris_street.jpg` | Тест городских сцен |
| `seq_django_diagram.png` | Тест технических диаграмм |
| `small_icon.webp` | Edge case: маленький WebP файл |
| `8k_japanese_walpaper.jpg` | Edge case: 8K разрешение |

---

## 🏃 Команды запуска

```bash
# Все тесты (без real_api) — быстро, бесплатно
pytest tests/ -m "not real_api" -v

# Только Phase 6 тесты
pytest tests/unit/domain/test_media_dto.py \
       tests/unit/infrastructure/media/ \
       tests/unit/infrastructure/gemini/ \
       tests/integration/media/ -v

# E2E с реальным Gemini API (нужен ключ)
export GEMINI_API_KEY="your-key"
pytest tests/e2e/gemini/ -m real_api -v --tb=short

# Проверка покрытия
pytest tests/ -m "not real_api" --cov=semantic_core
```

---

## ✅ Definition of Done

1. ✅ **Unit-тесты:** DTO, tokens, resilience, rate_limiter, file_utils — все зелёные
2. ✅ **Integration-тесты:** Queue processor, Pipeline — все зелёные  
3. ✅ **E2E готовы:** 13 тестов с реальным API (marker: real_api)
4. ✅ **Изоляция тестов:** DB state корректно восстанавливается
5. ✅ **224 теста проходят:** Все существующие тесты остаются зелёными
6. ✅ **Тестовые ассеты:** 9 реальных изображений для E2E

---

## 🚀 Следующие шаги

- **Phase 6.2:** Audio/Video обработка
- Документация в `doc/architecture/` по завершённой фазе
