# 🔥 Phase 14: Media Content Crisis

> **Статус:** 🔄 В РАЗРАБОТКЕ  
> **Цель:** Устранить потери 67-95% данных в медиа-контенте

---

## 📖 Содержание фазы

### 71. Media Content Truncation Crisis

**Файл:** [71_media_content_truncation_crisis.md](71_media_content_truncation_crisis.md)

Обнаружение катастрофы: 67-95% потеря данных в медиа-файлах, hardcoded лимиты 8k токенов.

**Проблема:**

- Audio: 83 минуты → 8k токенов (потеря 67%)
- Video: OCR 65k токенов → 8k (потеря 87%)
- Long video: 360k токенов → 8k (потеря 95%)

---

### 72. Multi-Chunk Media Architecture

**Файл:** [72_multi_chunk_media_architecture.md](72_multi_chunk_media_architecture.md)

Решение кризиса: summary + transcript chunks, конфигурируемые лимиты, полное покрытие контента.

**Архитектура:**

- **Summary chunk** (max 2k tokens): краткое описание
- **Transcript chunks** (по 8k tokens): полный контент
- **OCR chunks** (через SmartSplitter): структурированный текст

---

### 73. Multilingual Media Analysis

**Файл:** [73_multilingual_media_analysis.md](73_multilingual_media_analysis.md)

Настройка языка вывода через конфиг: template промпты, инъекция параметров, backward compatibility.

**Конфиг:**

```toml
[media.analysis]
language = "Russian"  # Gemini ответит на русском!
```

---

### 74. Media Smart Splitter Integration

**Файл:** [74_media_smart_splitter_integration.md](74_media_smart_splitter_integration.md)

`SmartSplitter` для OCR-текста: изоляция кода в скринкастах, Markdown промпты, `code_ratio` мониторинг.

**Решение:**

- Gemini генерирует Markdown (инструкции в промптах)
- `SmartSplitter` парсит через `MarkdownNodeParser`
- Code blocks изолируются в `ChunkType.CODE`
- Мониторинг false positives через `code_ratio > 0.5`

---

### 75. Processing Steps Architecture

**Файл:** [75_processing_steps_architecture.md](75_processing_steps_architecture.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.1.0)

Модульная step-based архитектура для media processing: `MediaContext`, `BaseProcessingStep`, `MediaPipeline`.

**Компоненты:**

- **MediaContext** (frozen dataclass): immutable контейнер данных
- **BaseProcessingStep** (ABC): абстракция для шагов обработки
- **MediaPipeline**: executor для координации шагов
- **Service Locator**: зависимости через `context.services`

**Тестирование:**

- ✅ 13 unit-тестов MediaContext (immutability, with_chunks, service locator)
- ✅ 12 unit-тестов MediaPipeline (execution, error handling, logging)
- ✅ 100% passing

---

### 76. Smart Steps: Summary & Transcription

**Файл:** [76_smart_steps_summary_transcription.md](76_smart_steps_summary_transcription.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.1.1)

Реализация `SummaryStep` и `TranscriptionStep` — конкретных шагов обработки медиа-контента.

**SummaryStep:**

- Извлечение description из analysis
- Поддержка image/audio/video с правильными ChunkType
- Флаг `include_keywords` для управления metadata
- 14 unit-тестов (всё покрыто)

**TranscriptionStep:**

- Разбивка транскрипции через BaseSplitter (Constructor Injection)
- `should_run()`: проверка наличия transcription
- Обогащение metadata: `role='transcript'`, `parent_media_path`
- 11 unit-тестов (включая edge cases)

**Тестирование:**

- ✅ 14 тестов SummaryStep (0.08s)
- ✅ 11 тестов TranscriptionStep (0.09s)
- ✅ 100% passing

---

### 77. OCR Step — Smart Parsing для распознанного текста

**Файл:** [77_smart_step_ocr.md](77_smart_step_ocr.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.1.1)

Реализация `OCRStep` с Markdown-парсингом для изоляции code blocks в видео-скринкастах.

**Ключевые фичи:**

- **parser_mode:** `"markdown"` (code detection) | `"plain"` (simple text)
- **Code Ratio Monitoring:** WARNING при > 50% CODE chunks (false positives)
- **MediaType.TEXT Bug Fix:** исправлен несуществующий `MediaType.MARKDOWN`
- **Constructor Injection:** `splitter: BaseSplitter`

**Тестирование:**

- ✅ 15 тестов OCRStep (0.09s)
- ✅ Покрытие: should_run, parser_mode, code_ratio, metadata enrichment
- ✅ 100% passing

**Итоги Phase 14.1.1:**

```
40 unit-тестов steps + 25 unit-тестов core = 65 тестов
0.26s execution
100% passing
```

---

### 78. TimecodeParser — Парсинг таймкодов из транскрипций

**Файл:** [78_timecode_parser.md](78_timecode_parser.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.1.2)

Утилита для парсинга `[MM:SS]`/`[HH:MM:SS]` из audio/video транскрипций + интеграция в `TranscriptionStep`.

**Ключевые фичи:**

- **TimecodeParser:** regex-based парсинг таймкодов из текста
- **Валидация:** `max_duration_seconds`, `strict_ordering` (optional)
- **Timecode Inheritance:** первый chunk=0, последующие=last+delta
- **TranscriptionStep.enable_timecodes:** флаг для включения/отключения парсинга
- **Metadata enrichment:** `start_seconds` (всегда), `timecode_original` (если распарсен)

**Тестирование:**

- ✅ 27 тестов TimecodeParser (Basic, ParseAll, Validation, Inheritance, EdgeCases)
- ✅ 7 новых тестов TranscriptionStep (timecode integration)
- ✅ 18 total тестов TranscriptionStep (11 базовых + 7 timecode)
- ✅ 100% passing (0.16s)

**Commits:**

- `fd4e26b` — TimecodeParser utility (27 тестов)
- `15c3960` — TranscriptionStep integration (7 новых тестов + RAG fix)

**Итоги Phase 14.1.2 (Partial):**

```
67 unit-тестов (40 steps + 27 timecode) + 135 core/rag/context = 202 теста
0.35s execution
100% passing
```

---

### 79. Analyzer Migration — response.parsed вместо json.loads()

**Файл:** [79_analyzer_migration_response_parsed.md](79_analyzer_migration_response_parsed.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.1.3)

Рефакторинг audio/video/image analyzers: миграция с `json.loads()` на `response.parsed` (Pydantic).

**Ключевые изменения:**

- **Удалён json.loads():** Из всех 3 analyzers (audio, video, image)
- **response.parsed:** Автоматический парсинг в Pydantic объекты
- **Type-safe доступ:** `data.field` вместо `data.get("field", default)`
- **Убран error handling:** try/except json.JSONDecodeError (Gemini SDK гарантирует валидность)
- **Удалён импорт json:** Из всех analyzers

**Выгоды:**

- ✅ -27 lines code (774 → 747 lines)
- ✅ Type safety: dict → Pydantic objects
- ✅ IDE autocomplete для полей схем
- ✅ Меньше boilerplate (no .get() с defaults)

**Тестирование:**

- ✅ 202/202 тестов passing (no regressions)
- ✅ Backward compatibility сохранена

**Commit:**

- `1e0dc44` — Миграция analyzers на response.parsed (Pydantic)

**Итоги Phase 14.1.3:**

```
202 unit-теста (100% passing)
-27 lines code
+Type safety
Phase 14.1: Smart Steps + Advanced Features — ✅ COMPLETED
```

---

### 80. E2E Testing & MediaPipeline Integration

**Файл:** [80_e2e_testing_mediapipeline_integration.md](80_e2e_testing_mediapipeline_integration.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.1.4)

Финальная интеграция MediaPipeline в SemanticCore + E2E валидация timecode parsing и user_instructions.

**Ключевые изменения:**

- **MediaPipeline Integration:** Замена legacy `_build_media_chunks()` на модульную архитектуру
- **Удалён legacy код:** `_split_transcription_into_chunks()` и `_split_ocr_into_chunks()` (-82 LOC)
- **Bugfix Path serialization:** `metadata["source"] = str(path)` вместо Path объектов
- **E2E Test Suite:** 6 тестов для валидации полной интеграции

**E2E Tests (6/6 PASSED):**

1. `test_audio_with_timecodes` — проверка парсинга `[MM:SS]` → `start_seconds`
2. `test_timecode_inheritance` — наследование таймкодов для чанков без меток
3. `test_first_chunk_without_timecode_is_zero` — edge case (нет таймкода → 0)
4. `test_user_prompt_injection_audio` — передача user_prompt в audio analyzer
5. `test_user_prompt_injection_video` — передача user_prompt в video analyzer
6. `test_timecode_validation_max_duration` — отбрасывание невалидных таймкодов

**Архитектурные улучшения:**

- ✅ **Модульность:** Шаги независимы, переиспользуются
- ✅ **Тестируемость:** Изолированное тестирование компонентов
- ✅ **Расширяемость:** `pipeline.register_step()` для новых шагов
- ✅ **Code cleanup:** -82 LOC legacy кода

**Commits:**

- `6e66974` — Bugfix: Path objects JSON serialization
- `42b0d30` — MediaPipeline Integration + E2E Tests

**Итоги Phase 14.1 (FINAL):**

```
214 total tests (208 unit + 6 E2E)
6 статей (75-80)
7 commits
-109 LOC (82 + 27)
100% passing
✅ Phase 14.1 — COMPLETED!
```

---

### 81. MediaService & Aggregation Layer

**Файл:** [81_mediaservice_aggregation_layer.md](81_mediaservice_aggregation_layer.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.2)

Сервисный слой для агрегации разрозненных медиа-чанков в структурированные DTO.

**Проблема:**

После Phase 14.1 медиа разбивается на множество чанков (summary, transcript, OCR).
UI/CLI приходится вручную собирать данные → дублирование логики.

**Решение: MediaService**

Единая точка агрегации с тремя методами:
- `get_media_details(doc_id)` → `MediaDetails` (полная информация)
- `get_timeline(doc_id)` → `list[TimelineItem]` (навигация по таймкодам)
- `get_chunks_by_role(doc_id, role)` → `list[Chunk]` (фильтрация)

**DTO Models:**
- **TimelineItem:** chunk_id, start_seconds, content_preview, formatted_time
- **MediaDetails:** summary, full_transcript, full_ocr_text, timeline, keywords, +properties

**Ключевые фичи:**
- ✅ Автоматическое склеивание transcript/OCR в единый текст
- ✅ Timeline сортируется по start_seconds
- ✅ Properties: has_timeline, has_transcript, has_ocr, total_chunks
- ✅ Форматирование времени: 65 → "01:05", 3665 → "1:01:05"

**Тестирование:**
- ✅ 9 unit-тестов (100% passing)
- ✅ Fixture-based mocking (Peewee ORM)
- ✅ Обработка исключений через `peewee.DoesNotExist`

**Commit:** `a7045fd`

**Итоги Phase 14.2:**

```
9 unit-тестов MediaService
1024 total tests в проекте
Сокращение кода: 30+ строк → 4 строки (Flask routes)
✅ Phase 14.2 — COMPLETED!
```

---

### 82. Configuration & Template Injection

**Файл:** [82_configuration_template_injection.md](82_configuration_template_injection.md)  
**Статус:** ✅ ЗАВЕРШЕНО (Phase 14.3.1)

MediaConfig models + Template Injection pattern для гибкой кастомизации промптов и chunk sizes.

**Проблема:**

Система негибкая после Phase 14.1-14.2:
- ❌ Промпты захардкожены — нельзя кастомизировать под домен
- ❌ Chunk size единый — transcript и OCR используют одинаковый размер
- ❌ Parser mode статичен — OCR всегда Markdown

**Решение: MediaConfig + Template Injection**

**Структура:**

- **MediaPromptsConfig:** `audio_instructions`, `image_instructions`, `video_instructions`
- **MediaChunkSizesConfig:** `summary_chunk_size`, `transcript_chunk_size`, `ocr_text_chunk_size`, `ocr_code_chunk_size` (с `ge`/`le` validation)
- **MediaProcessingConfig:** `ocr_parser_mode` (pattern validation), `enable_timecodes`, `max_timeline_items`

**Template Injection Pattern:**

```python
DEFAULT_SYSTEM_PROMPT = """You are an audio analyst...
{custom_instructions}

Return a JSON with {{...}}
"""

def _build_system_prompt(self) -> str:
    instructions = f"CUSTOM INSTRUCTIONS:\n{self.custom_instructions}\n"
    return DEFAULT_SYSTEM_PROMPT.format(
        custom_instructions=instructions,
        language=self.output_language,
    )
```

**Гарантии:**
- ✅ Placeholders ПЕРЕД JSON schema — безопасная инъекция
- ✅ Double braces `{{...}}` — не ломаются от `.format()`
- ✅ Unicode handling — корректная обработка спецсимволов

**TOML Support:**

```toml
[media.prompts]
audio_instructions = "Extract medical terms, diagnoses..."

[media.chunk_sizes]
transcript_chunk_size = 1000  # Маленькие для точности
ocr_code_chunk_size = 3000    # Большие чтобы не резать код

[media.processing]
ocr_parser_mode = "plain"  # markdown | plain
```

**Тестирование:**
- ✅ 19 config tests (validation, TOML loading, nested parsing)
- ✅ 19 template injection tests (escaping, JSON schema order, edge cases)
- ✅ 38/38 PASSED — 100% coverage

**Commit:** `d270238`

**Итоги Phase 14.3.1:**

```
38 новых тестов (19 config + 19 template injection)
1062 total tests в проекте (1024 + 38)
4 новых Pydantic models с валидацией
✅ Phase 14.3.1 — COMPLETED!
```

---

## 🔗 Связанные фазы

- **Phase 4:** [Smart Parsing](../phase_4_smart_parsing/) — SmartSplitter для OCR
- **Phase 6:** [Multimodal](../phase_6_multimodal/) — media analyzers
- **Phase 13:** [Audit](../phase_13_audit/) — обнаружение кризиса

---

## 🚀 Phase 14.1.2 Preview

**Следующий шаг:** Advanced Features

Реализация FrameDescriptionStep, TimecodeParser, user_instructions для расширения функциональности pipeline.

---

**← [Вернуться к оглавлению](../00_overview.md)**
