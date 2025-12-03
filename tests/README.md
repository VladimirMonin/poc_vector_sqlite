# 🧪 Тесты Semantic Core

> 470+ тестов, покрывающих от unit-логики до E2E с реальными API.

---

## 📂 Структура

```
tests/
├── conftest.py              # Все фикстуры проекта
├── unit/                    # Изолированные unit-тесты
│   ├── core/                # BatchManager, очереди
│   ├── domain/              # DTO-модели (Document, Chunk, SearchResult)
│   ├── infrastructure/      # Инфраструктурный слой
│   │   ├── batching/        # Batch API логика
│   │   ├── gemini/          # RateLimiter, Resilience
│   │   └── media/           # Токены, FileUtils
│   ├── integrations/        # SemanticIndex, SearchProxy
│   └── processing/          # Парсинг и контекст
│       ├── context/         # HierarchicalContextStrategy
│       ├── parsers/         # MarkdownNodeParser
│       └── splitters/       # SmartSplitter
├── integration/             # Тесты с реальной БД (in-memory)
│   ├── batching/            # Async ingestion workflow
│   ├── descriptor/          # ORM + SemanticIndex
│   ├── granular_search/     # Поиск по чанкам с фильтрами
│   ├── media/               # Pipeline + QueueProcessor
│   └── search/              # Гибридный поиск (RRF)
├── e2e/                     # End-to-End с реальными API
│   └── gemini/              # Реальные вызовы Gemini Vision/Audio/Video
├── fixtures/                # Тестовые данные
│   ├── images/              # Генерируемые картинки (red_square.png)
│   ├── media/               # Markdown, audio, video фикстуры
│   │   ├── audio/           # speech.mp3, noise.wav
│   │   ├── markdown/        # post_with_media.md
│   │   └── video/           # slides.mp4, talking_head.mp4
│   └── real_docs/           # evil.md и другие edge cases
├── asests/                  # Реальные картинки для E2E
└── _archived/               # Устаревшие тесты (на удаление)
```

---

## 🔧 Ключевые фикстуры

### База данных

| Фикстура | Scope | Описание |
|----------|-------|----------|
| `in_memory_db` | function | SQLite :memory: с sqlite-vec extension |
| `media_db` | function | Временная БД с MediaTaskModel |
| `test_db` | function | Старый API (для backward compatibility) |

### Embedder и Core

| Фикстура | Описание |
|----------|----------|
| `mock_embedder` | Детерминированные векторы через MD5-хеш |
| `semantic_core` | SemanticCore с mock embedder и in-memory DB |
| `smart_semantic_core` | + SmartSplitter + HierarchicalContext |

### Парсинг

| Фикстура | Описание |
|----------|----------|
| `markdown_parser` | MarkdownNodeParser instance |
| `smart_splitter` | SmartSplitter с настройками для тестов |
| `hierarchical_context` | HierarchicalContextStrategy |

### Media анализ

| Фикстура | Описание |
|----------|----------|
| `mock_image_analyzer` | MagicMock с MediaAnalysisResult |
| `mock_audio_analyzer` | + transcription, participants |
| `mock_video_analyzer` | + frames, ocr_text |
| `rate_limiter` | RateLimiter (60 RPM) |
| `media_queue_processor` | Готовый QueueProcessor с моками |

### Тестовые файлы

| Фикстура | Путь |
|----------|------|
| `red_square_path` | fixtures/images/red_square.png (генерируется) |
| `evil_md_path` | fixtures/real_docs/evil.md |
| `speech_audio_path` | fixtures/media/audio/speech.mp3 |
| `slides_video_path` | fixtures/media/video/slides.mp4 |

---

## 🏃 Запуск тестов

```bash
# Все тесты
poetry run pytest tests/

# Только unit
poetry run pytest tests/unit/

# Только integration
poetry run pytest tests/integration/

# С покрытием
poetry run pytest tests/ --cov=semantic_core --cov-report=html

# Конкретный модуль
poetry run pytest tests/unit/processing/parsers/ -v

# По маркеру (пропустить реальные API)
poetry run pytest tests/ -m "not real_api"
```

---

## 🏷️ Маркеры

| Маркер | Описание |
|--------|----------|
| `@pytest.mark.real_api` | Тесты с реальными API-вызовами (медленные, платные) |

Тесты с маркером `real_api` находятся в `tests/e2e/` и требуют `GEMINI_API_KEY`.

---

## 📊 Покрытие по фазам

| Фаза | Описание | Основные тесты |
|------|----------|----------------|
| Phase 1 | SOLID архитектура | `test_phase_1_architecture.py` |
| Phase 2 | Storage Layer | `test_phase_2_storage.py` |
| Phase 3 | ORM Integration | `integration/descriptor/` |
| Phase 4 | Smart Parsing | `processing/parsers/`, `processing/context/` |
| Phase 5 | Async Batching | `unit/core/`, `integration/batching/` |
| Phase 6 | Multimodal | `infrastructure/media/`, `integration/media/` |

---

## 💡 Соглашения

1. **Unit vs Integration** — unit тесты не должны использовать реальную БД или API
2. **Mock-first** — для API-зависимостей используем MagicMock/AsyncMock
3. **Fixtures в conftest.py** — все общие фикстуры централизованы
4. **Генерируемые файлы** — картинки создаются фикстурами через Pillow
5. **Skip при отсутствии** — `pytest.skip()` если файл/зависимость недоступны

---

## 🔗 Связанные документы

- [Concept Instructions](../.github/instructions/concept.instructions.md) — общая архитектура
- [Phase 6.6 Report](../doc/ideas/phase_6/report_phase_6.6.md) — тестирование мультимодальности
