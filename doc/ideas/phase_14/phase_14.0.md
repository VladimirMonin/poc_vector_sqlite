# 🔴 КРИТИЧЕСКИЙ АРХИТЕКТУРНЫЙ ДЕФЕКТ: Медиа-контент кастрирован

**Дата обнаружения:** 2025-12-06  
**Обнаружено в ходе:** Phase 12 (Flask App) + Phase 13 (Human-First Testing)  
**Приоритет:** P0 — Критический  
**Влияние:** Семантический поиск по аудио/видео работает на ~15% от возможностей

---

## 📋 Оглавление

1. [Симптомы проблемы](#1-симптомы-проблемы)
2. [Корневые причины](#2-корневые-причины)
3. [Предыстория: как мы здесь оказались](#3-предыстория-как-мы-здесь-оказались)
4. [Технический анализ](#4-технический-анализ)
5. [Масштаб проблемы](#5-масштаб-проблемы)
6. [План исправления](#6-план-исправления)
7. [Рекомендации архитектора](#7-рекомендации-архитектора)

---

## 1. Симптомы проблемы

### Что наблюдает пользователь

При загрузке **3-минутного аудиофайла** через Flask App:

- ❌ В БД сохраняется **1 чанк** вместо ожидаемых 4-5
- ❌ Транскрипция содержит только **~50 секунд** из 180 секунд
- ❌ Ответ от Gemini API **длиннее**, чем сохранённый контент
- ❌ Semantic search находит только начало аудио

### Ожидаемое поведение

- ✅ Полная транскрипция 3 минут (~6000-8000 символов)
- ✅ 6-8 чанков по ~1000 символов каждый
- ✅ Семантический поиск по всему содержимому

---

## 2. Корневые причины

### Проблема #1: Жёсткий лимит `max_output_tokens=8192`

| Файл | Строка | Значение | Лимит модели |
|------|--------|----------|--------------|
| `semantic_core/infrastructure/gemini/audio_analyzer.py` | 168 | 8,192 | **65,536** |
| `semantic_core/infrastructure/gemini/video_analyzer.py` | 244 | 8,192 | **65,536** |
| `semantic_core/infrastructure/gemini/image_analyzer.py` | 148 | 1,024 | 65,536 |

**Суть:** Модель `gemini-2.5-flash-lite` может вернуть **65,536 токенов**, но код ограничивает до **8,192** — в 8 раз меньше!

### Проблема #2: 1 чанк на любое медиа (БЕЗ сплиттера)

| Файл | Строки | Что происходит |
|------|--------|----------------|
| `semantic_core/pipeline.py` | 300 | `_ingest_direct_media()` — 1 чанк |
| `semantic_core/pipeline.py` | 703 | `ingest_image()` — 1 чанк |
| `semantic_core/pipeline.py` | 849 | `ingest_audio()` — 1 чанк |
| `semantic_core/pipeline.py` | 995 | `ingest_video()` — 1 чанк |

**Суть:** Все медиа-методы создают ровно ОДИН чанк и сохраняют напрямую через `store.save(doc, [chunk])`, **минуя сплиттер**.

### Проблема #3: Silent Truncation эмбеддингов

Даже если транскрипция была бы полной (10,000 символов), Gemini Embedding API имеет лимит **~2000 токенов на вход**.

При одном чанке в 10,000 символов:

- Эмбеддинг создаётся только по первым ~4000-5000 символам
- Остальное **молча игнорируется**
- Semantic search находит только начало документа

### ~~Проблема #4: `chunk_size` не в конфигурации~~ ✅ ИСПРАВЛЕНО

| Параметр | Где задан | Можно менять? |
|----------|-----------|---------------|
| `chunk_size=1800` | `SemanticConfig` → `SmartSplitter` | ✅ Через `semantic.toml` |
| `code_chunk_size=2000` | `SemanticConfig` → `SmartSplitter` | ✅ Через `semantic.toml` |

**UPDATE (2025-12-06):** Проблема исправлена в рамках рефакторинга Phase 2-3. Параметры **уже** доступны в конфигурации!

---

## ✅ СТАТУС ИСПРАВЛЕНИЯ (Phase 14.5 - Декабрь 2025)

**Дата завершения:** 2025-12-10  
**Статус:** ✅ ПОЛНОСТЬЮ ЗАВЕРШЕНО

### Что было исправлено

#### 1. ✅ max_output_tokens увеличен до 65,536

- `audio_analyzer.py`, `video_analyzer.py`, `image_analyzer.py`
- Полная транскрипция и OCR без обрезки

#### 2. ✅ Multi-chunk architecture через MediaPipeline

- Phase 14.1: Step-based архитектура (SummaryStep, TranscriptionStep, OCRStep)
- Медиа разбивается на множество чанков с ролями: `summary`, `transcript`, `ocr`
- Splitter интегрирован во все steps

#### 3. ✅ OCR Markdown Parsing (Phase 14.5)

**Критическое улучшение:** Code blocks изолируются в отдельные чанки

**Реализация:**

- `OCRStep` теперь использует `MarkdownNodeParser` напрямую
- Code blocks (```python) детектятся и создаются как `ChunkType.CODE`
- Обычный текст → `ChunkType.TEXT`
- Разные `chunk_size` для кода (`ocr_code_chunk_size=2000`) и текста (`ocr_text_chunk_size=1800`)

**Файлы:**

- `semantic_core/processing/steps/ocr.py` — переработан
- `tests/unit/processing/steps/test_ocr_step.py` — 15+ unit-тестов
- `tests/integration/media/test_ocr_markdown_parsing.py` — 15+ интеграционных тестов с реальным MarkdownNodeParser

**Metadata enrichment:**

- `hierarchical_context` — breadcrumbs из заголовков Markdown
- `language` — язык code block (python, javascript, bash)
- `start_line`, `end_line` — позиция в исходном тексте
- `role="ocr"`, `parent_media_path`

#### 4. ✅ Конфигурация через TOML (Phase 14.3)

- `MediaChunkSizesConfig`: `summary_chunk_size`, `transcript_chunk_size`, `ocr_text_chunk_size`, `ocr_code_chunk_size`
- `MediaProcessingConfig`: `ocr_parser_mode` (markdown/plain), `enable_timecodes`
- `MediaPromptsConfig`: кастомные промпты для image/audio/video analysis

#### 5. ✅ MediaService & Aggregation Layer (Phase 14.2)

- `MediaService.get_media_details()` — агрегация всех чанков в `MediaDetails` DTO
- `MediaService.get_timeline()` — таймкоды для видео-плеера
- `MediaService.reprocess_document()` — реанализ с новыми промптами

#### 6. ✅ CLI Integration (Phase 14.3.4)

- `semantic reanalyze <doc_id>` — повторный анализ медиа
- `--prompt` для custom instructions
- `--force` для скриптов без подтверждения
- Rich UI: tables, panels, spinners

### Результаты

**Тестирование:**

- 193+ тестов для Phase 14 компонентов
- Unit-тесты: mock-based для изоляции
- Integration-тесты: с реальным MarkdownNodeParser
- E2E-тесты: полный pipeline с таймкодами

**Документация:**

- 15 архитектурных статей в `doc/architecture/phase_14_media_crisis/`
- Детальное описание каждого шага: от проблемы до решения

**Code quality:**

- SOLID принципы: SRP (MediaService), DI (steps), OCP (MediaPipeline)
- Type safety: Pydantic models для всех конфигов
- Logging: semantic logging с эмодзи и trace level
- -109 LOC удалено (legacy код), +2000 LOC добавлено (качественный код)

### Следующие шаги

- ⏸ Flask UI для медиа-плеера (Phase 12, отложено)
- 📝 Финальный отчёт Phase 14 (16_phase_14_final_report.md)

---

## 3. Предыстория: как мы здесь оказались

### Phase 6.0: Images + Queue (Июнь 2025)

**Планировалось:** (из `doc/ideas/phase_6/plan_phase_6.0_merged.md`, строка 405)
